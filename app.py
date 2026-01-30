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
    Filtra colunas essenciais de auditoria, incluindo tags de valores retidos.
    """
    mapping = {
        'Nota_Numero': ['numero', 'nfnr', 'numnf'],
        'Data_Emissao': ['dataemissao', 'dtemic', 'dtrem'],
        'Prestador_CNPJ': ['prestador_cnpj', 'prestador_cpfcnpj', 'prestador_identificacao'],
        'Prestador_Razao': ['prestador_razãosocial', 'prestador_xnome', 'prestador_razão'],
        'Tomador_CNPJ': ['tomador_cnpj', 'tomador_cpfcnpj', 'tomador_identificacao'],
        'Tomador_Razao': ['tomador_razãosocial', 'tomador_xnome', 'tomador_razão'],
        'Vlr_Bruto': ['valorservicos', 'vserv', 'vlrserv', 'valorbruto'],
        'Vlr_Liquido': ['valorliquido', 'vliq', 'vlrliq'],
        # Impostos Totais / Alíquotas
        'ISS_Total': ['valoriss', 'viss'],
        'ISS_Retido': ['issretido', 'vissret', 'iss_retido'],
        'PIS_Total': ['valorpis', 'vpis'],
        'PIS_Retido': ['pisretido', 'vpisret', 'pis_retido'],
        'COFINS_Total': ['valorcofins', 'vcofins'],
        'COFINS_Retido': ['cofinsretido', 'vcofinsret', 'cofins_retido'],
        'IRRF_Retido': ['valorir', 'vir', 'irrf_retido', 'virrf'],
        'CSLL_Retido': ['valorcsll', 'vcsll', 'csll_retido'],
        # Reforma Tributária
        'IBS_Valor': ['ibs_vlr', 'ibs_valor'],
        'CBS_Valor': ['cbs_vlr', 'cbs_valor'],
        'Servico_Descricao': ['discriminacao', 'xserv', 'infadic']
    }

    final_df_data = {}
    if 'Arquivo_Origem' in df.columns:
        final_df_data['Arquivo'] = df['Arquivo_Origem']

    for friendly_name, radicals in mapping.items():
        found_col = None
        for col in df.columns:
            # Verifica se algum radical está no nome da coluna (ignora case)
            if any(rad in col.lower() for rad in radicals):
                # Filtro extra para evitar endereços
                if not any(x in col.lower() for x in ['endereco', 'logradouro', 'uf', 'cep', 'bairro']):
                    found_col = col
                    break
        
        if found_col:
            final_df_data[friendly_name] = df[found_col]
        else:
            final_df_data[friendly_name] = "0.00" # Padrão para valores não encontrados

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
    st.subheader("Auditoria de Retenções Fiscais (Padrão Nacional)")

    uploaded_files = st.file_uploader("Upload de XML ou ZIP (incluindo pastas compactadas)", type=["xml", "zip"], accept_multiple_files=True)

    if uploaded_files:
        with st.spinner('Analisando retenções e impostos...'):
            df_raw = process_files(uploaded_files)
        
        if not df_raw.empty:
            df_final = simplify_and_filter(df_raw)

            st.success(f"Notas processadas: {len(df_final)}")
            
            st.write("### Tabela para Conferência de Escrituração")
            st.dataframe(df_final)

            # Geração do Excel formatado
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_final.to_excel(writer, index=False, sheet_name='Auditoria_Fisc')
                
                # Ajuste de colunas no Excel
                workbook = writer.book
                worksheet = writer.sheets['Auditoria_Fisc']
                header_format = workbook.add_format({'bold': True, 'bg_color': '#FFDEEF', 'border': 1})
                
                for col_num, value in enumerate(df_final.columns.values):
                    worksheet.write(0, col_num, value, header_format)
                    column_len = max(df_final[value].astype(str).str.len().max(), len(value)) + 2
                    worksheet.set_column(col_num, col_num, min(column_len, 40))

            st.download_button(
                label="📥 Baixar Planilha de Retenções",
                data=output.getvalue(),
                file_name="portal_servtax_retencoes.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.warning("Nenhum arquivo XML válido foi encontrado.")

if __name__ == "__main__":
    main()
