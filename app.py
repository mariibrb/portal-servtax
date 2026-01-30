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
    Filtra colunas com mapeamento reforçado para evitar 'None' nos dados principais.
    """
    # Mapeamento cirúrgico para os campos que você apontou
    mapping = {
        'Nota_Numero': ['numero', 'nfnr', 'nnfse', 'nrnotafiscal'],
        'Data_Emissao': ['dataemissao', 'dtemic', 'dtrem', 'dh_emi', 'dtaemi', 'data_hora'],
        
        # Ajuste fino Prestador (Procura o bloco e o campo)
        'Prestador_CNPJ': ['prestador_cnpj', 'prestador_cpfcnpj', 'prestador_cpf_cnpj', 'identificacaoprestador_cnpj'],
        'Prestador_Razao': ['prestador_razãosocial', 'prestador_xnome', 'prestador_razão', 'prestador_nome', 'prestador_identificacao_nome'],
        
        # Ajuste fino Tomador
        'Tomador_CNPJ': ['tomador_cnpj', 'tomador_cpfcnpj', 'tomador_cpf_cnpj', 'identificacaotomador_cnpj'],
        'Tomador_Razao': ['tomador_razãosocial', 'tomador_xnome', 'tomador_razão', 'tomador_nome', 'tomador_identificacao_nome'],
        
        # Valores e Impostos
        'Vlr_Bruto': ['valorservicos', 'vserv', 'vlrserv', 'valorbruto', 'v_serv'],
        'ISS_Retido': ['issretido', 'vissret', 'iss_retido', 'v_iss_ret'],
        'PIS_Retido': ['pisretido', 'vpisret', 'pis_retido'],
        'COFINS_Retido': ['cofinsretido', 'vcofinsret', 'cofins_retido'],
        'IRRF_Retido': ['valorir', 'vir', 'irrf_retido', 'virrf'],
        'CSLL_Retido': ['valorcsll', 'vcsll', 'csll_retido'],
        
        # Ajuste fino Descrição
        'Servico_Descricao': ['discriminacao', 'xserv', 'infadic', 'desc_serv', 'servico_discriminacao']
    }

    final_df_data = {}
    if 'Arquivo_Origem' in df.columns:
        final_df_data['Arquivo'] = df['Arquivo_Origem']

    for friendly_name, radicals in mapping.items():
        found_col = None
        # Prioriza colunas que contêm o termo exato no final (mais precisão)
        for col in df.columns:
            col_lower = col.lower()
            if any(rad in col_lower for rad in radicals):
                # Para CNPJ e Razão, verificamos se o radical casa com a origem (prestador/tomador)
                if 'prestador' in friendly_name.lower() and 'tomador' in col_lower:
                    continue
                if 'tomador' in friendly_name.lower() and 'prestador' in col_lower:
                    continue
                
                # Bloqueio de endereços
                if not any(x in col_lower for x in ['endereco', 'logradouro', 'uf', 'cep', 'bairro']):
                    found_col = col
                    break
        
        if found_col:
            # Tratamento para valores numéricos
            if any(x in friendly_name for x in ['Vlr', 'ISS', 'PIS', 'COFINS', 'IR', 'CSLL']):
                final_df_data[friendly_name] = pd.to_numeric(df[found_col], errors='coerce').fillna(0.0)
            else:
                final_df_data[friendly_name] = df[found_col]
        else:
            final_df_data[friendly_name] = "Não localizado"

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
    st.subheader("Auditoria Fiscal: Correção de Mapeamento de Dados")

    uploaded_files = st.file_uploader("Upload de XML ou ZIP", type=["xml", "zip"], accept_multiple_files=True)

    if uploaded_files:
        with st.spinner('Refinando captura de CNPJ, Datas e Descrições...'):
            df_raw = process_files(uploaded_files)
        
        if not df_raw.empty:
            df_final = simplify_and_filter(df_raw)

            st.success(f"Notas processadas: {len(df_final)}")
            
            st.write("### Conferência Detalhada")
            st.dataframe(df_final)

            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_final.to_excel(writer, index=False, sheet_name='Auditoria')
                
                workbook = writer.book
                worksheet = writer.sheets['Auditoria']
                header_fmt = workbook.add_format({'bold': True, 'bg_color': '#FF69B4', 'font_color': 'white'})
                
                for i, col in enumerate(df_final.columns):
                    worksheet.write(0, i, col, header_fmt)
                    worksheet.set_column(i, i, 20)

            st.download_button(
                label="📥 Baixar Excel Corrigido",
                data=output.getvalue(),
                file_name="servtax_conferencia_fina.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.warning("Nenhum dado encontrado.")

if __name__ == "__main__":
    main()
