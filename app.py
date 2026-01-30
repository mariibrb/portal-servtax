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
    Filtra colunas essenciais usando busca por radical para evitar valores 'None'.
    """
    # Mapeamento por radicais (mais chance de acerto em diferentes padrões de prefeitura)
    mapping = {
        'Nota_Numero': ['numero', 'nfnr', 'numnf'],
        'Data_Emissao': ['dataemissao', 'dtemic', 'dtrem'],
        'Prestador_CNPJ': ['prestador_cnpj', 'prestador_cpfcnpj', 'prestador_identificacao'],
        'Prestador_Razao': ['prestador_razãosocial', 'prestador_xnome'],
        'Tomador_CNPJ': ['tomador_cnpj', 'tomador_cpfcnpj', 'tomador_identificacao'],
        'Tomador_Razao': ['tomador_razãosocial', 'tomador_xnome'],
        'Vlr_Bruto': ['valorservicos', 'vserv', 'vlrserv'],
        'Vlr_Liquido': ['valorliquido', 'vliq'],
        'ISS': ['valoriss', 'viss'],
        'PIS': ['valorpis', 'vpis'],
        'COFINS': ['valorcofins', 'vcofins'],
        'IRRF': ['valorir', 'vir'],
        'CSLL': ['valorcsll', 'vcsll'],
        'IBS': ['ibs_vlr', 'ibs_valor'],
        'CBS': ['cbs_vlr', 'cbs_valor'],
        'Servico_Descricao': ['discriminacao', 'xserv', 'infadic']
    }

    final_df_data = {}
    if 'Arquivo_Origem' in df.columns:
        final_df_data['Arquivo'] = df['Arquivo_Origem']

    # Para cada coluna que desejamos no Excel final
    for friendly_name, radicals in mapping.items():
        # Procura nas colunas reais do DataFrame por algum radical
        found_col = None
        for col in df.columns:
            if any(rad in col.lower() for rad in radicals):
                # Bloqueio de endereços para não pegar CNPJ de endereço por erro
                if not any(x in col.lower() for x in ['endereco', 'logradouro', 'uf', 'cep']):
                    found_col = col
                    break
        
        if found_col:
            final_df_data[friendly_name] = df[found_col]
        else:
            final_df_data[friendly_name] = "Não encontrado"

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
    st.subheader("Auditoria Fiscal: Captura Inteligente de Dados")

    uploaded_files = st.file_uploader("Suba seus XMLs ou ZIPs", type=["xml", "zip"], accept_multiple_files=True)

    if uploaded_files:
        with st.spinner('Mapeando tags fiscais...'):
            df_raw = process_files(uploaded_files)
        
        if not df_raw.empty:
            df_final = simplify_and_filter(df_raw)

            st.success(f"Notas processadas: {len(df_final)}")
            
            # Mostra o resultado final
            st.write("### Dados para Conferência")
            st.dataframe(df_final)

            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_final.to_excel(writer, index=False, sheet_name='PortalServTax')
            
            st.download_button(
                label="📥 Baixar Planilha de Auditoria",
                data=output.getvalue(),
                file_name="auditoria_portal_servtax.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.warning("Nenhum arquivo XML detectado.")

if __name__ == "__main__":
    main()
