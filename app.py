import streamlit as st
import pandas as pd
import xmltodict
import io
import zipfile

# Configuração da Página
st.set_page_config(page_title="Portal ServTax", layout="wide", page_icon="📑")

# Estilo Visual (Rihanna)
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;700&family=Plus+Jakarta+Sans:wght@400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Plus Jakarta Sans', sans-serif; }
    h1, h2, h3 { font-family: 'Montserrat', sans-serif; color: #FF69B4; }
    .stButton>button { background-color: #FF69B4; color: white; border-radius: 10px; border: none; font-weight: bold; width: 100%; height: 3em; }
    .stButton>button:hover { background-color: #FFDEEF; color: #FF69B4; border: 1px solid #FF69B4; }
    [data-testid="stFileUploadDropzone"] { border: 2px dashed #FF69B4; background-color: #FFDEEF; }
    </style>
    """, unsafe_allow_html=True)

def flatten_dict(d, parent_key='', sep='_'):
    items = []
    for k, v in d.items():
        clean_k = k.split(':')[-1] if ':' in k else k
        new_key = f"{parent_key}{sep}{clean_k}" if parent_key else clean_k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        elif isinstance(v, list):
            for i, item in enumerate(v):
                if isinstance(item, dict):
                    items.extend(flatten_dict(item, f"{new_key}_{i}", sep=sep).items())
                else:
                    items.append((f"{new_key}_{i}", item))
        else:
            items.append((new_key, v))
    return dict(items)

def simplify_and_filter(df):
    """
    Filtro de busca profunda: varre o DataFrame procurando padrões de fim de tag (sufixos)
    para garantir que nenhum campo essencial fique como None.
    """
    final_df_data = {}
    if 'Arquivo_Origem' in df.columns:
        final_df_data['Arquivo'] = df['Arquivo_Origem']

    # Definição de busca por sufixos e contextos
    # O código vai procurar: 'Algum radical no nome da coluna' AND 'Deve conter termo X' AND 'Não deve conter termo Y'
    targets = {
        'Nota_Numero': {'rads': ['numero', 'nnfse', 'numnf', 'nfnr'], 'must': [], 'not': []},
        'Data_Emissao': {'rads': ['dataemissao', 'dtemic', 'dtrem', 'dhemi', 'dtaemi', 'datahora'], 'must': [], 'not': []},
        
        'Prestador_CNPJ': {'rads': ['cnpj', 'cpfcnpj'], 'must': ['prestador'], 'not': ['tomador', 'intermediario']},
        'Prestador_Razao': {'rads': ['razaosocial', 'xnome', 'razao', 'nome'], 'must': ['prestador'], 'not': ['tomador', 'intermediario', 'endereco']},
        
        'Tomador_CNPJ': {'rads': ['cnpj', 'cpfcnpj'], 'must': ['tomador'], 'not': ['prestador', 'intermediario']},
        'Tomador_Razao': {'rads': ['razaosocial', 'xnome', 'razao', 'nome'], 'must': ['tomador'], 'not': ['prestador', 'intermediario', 'endereco']},
        
        'Vlr_Bruto': {'rads': ['valorservicos', 'vserv', 'vlrserv', 'valorbruto', 'vlrbruto'], 'must': [], 'not': ['retido', 'liquido']},
        'ISS_Retido': {'rads': ['issretido', 'vissret', 'iss_retido', 'valoriss'], 'must': ['retido'], 'not': []},
        'PIS_Retido': {'rads': ['pisretido', 'vpisret', 'pis_retido', 'valorpis'], 'must': ['retido'], 'not': []},
        'COFINS_Retido': {'rads': ['cofinsretido', 'vcofinsret', 'cofins_retido', 'valorcofins'], 'must': ['retido'], 'not': []},
        'IRRF_Retido': {'rads': ['valorir', 'vir', 'irrf_retido', 'virrf'], 'must': ['retido'], 'not': []},
        'CSLL_Retido': {'rads': ['valorcsll', 'vcsll', 'csll_retido'], 'must': ['retido'], 'not': []},
        
        'Servico_Descricao': {'rads': ['discriminacao', 'xserv', 'infadic', 'desc_serv', 'itemlistaservico'], 'must': [], 'not': ['prestador', 'tomador']}
    }

    for friendly_name, rules in targets.items():
        found_val = None
        for col in df.columns:
            c_low = col.lower()
            # 1. Verifica se tem algum dos radicais
            if any(r in c_low for r in rules['rads']):
                # 2. Verifica se atende aos critérios de inclusão (ex: tem que ter 'prestador')
                if all(m in c_low for m in rules['must']):
                    # 3. Verifica se atende aos critérios de exclusão (ex: não pode ter 'endereco')
                    if not any(n in c_low for n in rules['not'] + ['endereco', 'logradouro', 'uf', 'cep', 'bairro']):
                        # Priorizamos colunas que não estejam vazias (NaN)
                        if found_val is None or pd.isna(found_val):
                             found_val = df[col]
        
        if found_val is not None:
            # Tratamento numérico para impostos e valores
            if any(x in friendly_name for x in ['Vlr', 'ISS', 'PIS', 'COFINS', 'IR', 'CSLL']):
                final_df_data[friendly_name] = pd.to_numeric(found_val, errors='coerce').fillna(0.0)
            else:
                final_df_data[friendly_name] = found_val.fillna("Não Identificado")
        else:
            final_df_data[friendly_name] = 0.0 if 'Vlr' in friendly_name or 'Retido' in friendly_name else "Não Localizado"

    return pd.DataFrame(final_df_data)

def extract_xml_from_zip(zip_data, extracted_list):
    with zipfile.ZipFile(io.BytesIO(zip_data)) as z:
        for file_info in z.infolist():
            if file_info.filename.lower().endswith('.xml'):
                with z.open(file_info.filename) as xml_file:
                    extracted_list.append({'name': file_info.filename, 'content': xml_file.read()})
            elif file_info.filename.lower().endswith('.zip'):
                with z.open(file_info.filename) as inner_zip:
                    extract_xml_from_zip(inner_zip.read(), extracted_list)

def process_files(uploaded_files):
    xml_contents = []
    for uploaded_file in uploaded_files:
        content = uploaded_file.read()
        if uploaded_file.name.lower().endswith('.xml'):
            xml_contents.append({'name': uploaded_file.name, 'content': content})
        elif uploaded_file.name.lower().endswith('.zip'):
            extract_xml_from_zip(content, xml_contents)
            
    extracted_data = []
    for xml_item in xml_contents:
        try:
            data_dict = xmltodict.parse(xml_item['content'])
            flat_data = flatten_dict(data_dict)
            flat_data['Arquivo_Origem'] = xml_item['name']
            extracted_data.append(flat_data)
        except:
            continue
    return pd.DataFrame(extracted_data)

def main():
    st.title("📑 Portal ServTax")
    st.subheader("Auditoria Fiscal: Motor de Busca Profunda (Anti-None)")

    uploaded_files = st.file_uploader("Upload de XML ou ZIP", type=["xml", "zip"], accept_multiple_files=True)

    if uploaded_files:
        with st.spinner('Escaneando camadas do XML para encontrar dados perdidos...'):
            df_raw = process_files(uploaded_files)
        
        if not df_raw.empty:
            df_final = simplify_and_filter(df_raw)

            st.success(f"Notas processadas: {len(df_final)}")
            
            st.write("### Conferência de Auditoria")
            st.dataframe(df_final)

            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_final.to_excel(writer, index=False, sheet_name='Auditoria')
                
                workbook = writer.book
                worksheet = writer.sheets['Auditoria']
                header_fmt = workbook.add_format({'bold': True, 'bg_color': '#FF69B4', 'font_color': 'white', 'border': 1})
                
                for i, col in enumerate(df_final.columns):
                    worksheet.write(0, i, col, header_fmt)
                    worksheet.set_column(i, i, 20)

            st.download_button(
                label="📥 Baixar Excel Sem Erros",
                data=output.getvalue(),
                file_name="portal_servtax_final.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.warning("Nenhum dado encontrado.")

if __name__ == "__main__":
    main()
