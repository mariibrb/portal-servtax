import streamlit as st
import pandas as pd
import xmltodict
import io
import zipfile

# Configuração da Página
st.set_page_config(page_title="Portal ServTax", layout="wide", page_icon="📑")

# Estilo Rihanna
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
    if not isinstance(d, dict): return {}
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
    Motor de Busca por Intersecção: Localiza os campos ignorando a estrutura de pastas
    do XML de cada prefeitura, corrigindo NameErrors.
    """
    final_df_data = {}
    if 'Arquivo_Origem' in df.columns:
        final_df_data['Arquivo'] = df['Arquivo_Origem']

    # Regras de intersecção baseadas nos seus XMLs reais (Nacional e SP)
    rules = {
        'Nota_Numero': [['numero', 'nfe'], ['nnfse'], ['nnf'], ['nNF']],
        'Data_Emissao': [['data', 'emissao'], ['dhproc'], ['dhemi'], ['datahora']],
        
        # PRESTADOR
        'Prestador_CNPJ': [['prestador', 'cnpj'], ['emit', 'cnpj'], ['prestador', 'cpf']],
        'Prestador_Razao': [['prestador', 'razao'], ['emit', 'xnome'], ['prestador', 'nome'], ['emit', 'razao']],
        
        # TOMADOR
        'Tomador_CNPJ': [['tomador', 'cnpj'], ['toma', 'cnpj'], ['dest', 'cnpj'], ['tomador', 'cpf']],
        'Tomador_Razao': [['tomador', 'razao'], ['toma', 'xnome'], ['dest', 'xnome'], ['tomador', 'nome']],
        
        # VALORES
        'Vlr_Bruto': [['valorservicos'], ['vserv'], ['valorbruto'], ['vlrbruto'], ['vnf']],
        
        # IMPOSTOS
        'ISS_Valor': [['iss', 'valor'], ['viss'], ['valoriss'], ['iss', 'retido']],
        'PIS_Retido': [['pis', 'retido'], ['vpis'], ['valorpis']],
        'COFINS_Retido': [['cofins', 'retido'], ['vcofins'], ['valorcofins']],
        'IRRF_Retido': [['ir', 'retido'], ['vir'], ['valorir'], ['virrf']],
        'CSLL_Retido': [['csll', 'retido'], ['vcsll'], ['valorcsll']],
        
        # DESCRIÇÃO
        'Servico_Descricao': [['discriminacao'], ['xdescserv'], ['xserv'], ['infcpl'], ['xprod']]
    }

    for friendly_name, condition_groups in rules.items():
        found_series = None
        for col in df.columns:
            c_low = col.lower()
            
            # Verifica se a coluna possui TODAS as palavras de um dos grupos
            for group in condition_groups:
                if all(word in c_low for word in group):
                    # Filtro de segurança: não misturar Prestador com Tomador
                    if 'prestador' in friendly_name.lower() and ('tomador' in c_low or 'toma' in c_low or 'dest' in c_low):
                        continue
                    if 'tomador' in friendly_name.lower() and ('prestador' in c_low or 'emit' in c_low):
                        continue
                    
                    # Prioriza a coluna que tiver dados preenchidos
                    current_series = df[col]
                    if found_series is None or (isinstance(found_series, pd.Series) and found_series.isnull().all()):
                        found_series = current_series
                        break

        if found_series is not None:
            if any(x in friendly_name for x in ['Vlr', 'ISS', 'PIS', 'COFINS', 'IR', 'CSLL']):
                final_df_data[friendly_name] = pd.to_numeric(found_series, errors='coerce').fillna(0.0)
            else:
                final_df_data[friendly_name] = found_series.fillna("Dado Ausente")
        else:
            final_df_data[friendly_name] = 0.0 if any(x in friendly_name for x in ['Vlr', 'ISS', 'PIS', 'COFINS', 'IR', 'CSLL']) else "NÃO LOCALIZADO"

    return pd.DataFrame(final_df_data)

def extract_xml_from_zip(zip_data, extracted_list):
    try:
        with zipfile.ZipFile(io.BytesIO(zip_data)) as z:
            for file_info in z.infolist():
                if file_info.filename.lower().endswith('.xml'):
                    with z.open(file_info.filename) as xml_file:
                        extracted_list.append({'name': file_info.filename, 'content': xml_file.read()})
                elif file_info.filename.lower().endswith('.zip'):
                    with z.open(file_info.filename) as inner_zip:
                        extract_xml_from_zip(inner_zip.read(), extracted_list)
    except: pass

def process_files(uploaded_files):
    all_extracted_data = []
    for uploaded_file in uploaded_files:
        content = uploaded_file.read()
        if uploaded_file.name.lower().endswith('.xml'):
            all_extracted_data.append({'name': uploaded_file.name, 'content': content})
        elif uploaded_file.name.lower().endswith('.zip'):
            extract_xml_from_zip(content, all_extracted_data)
            
    final_rows = []
    for item in all_extracted_data:
        try:
            data_dict = xmltodict.parse(item['content'])
            if isinstance(data_dict, list):
                for sub_item in data_dict:
                    flat = flatten_dict(sub_item)
                    flat['Arquivo_Origem'] = item['name']
                    final_rows.append(flat)
            else:
                flat_data = flatten_dict(data_dict)
                flat_data['Arquivo_Origem'] = item['name']
                final_rows.append(flat_data)
        except: continue
    return pd.DataFrame(final_rows)

def main():
    st.title("📑 Portal ServTax")
    st.subheader("Auditoria Fiscal: Motor Unificado SP & Nacional")

    uploaded_files = st.file_uploader("Upload de XML ou ZIP", type=["xml", "zip"], accept_multiple_files=True)

    if uploaded_files:
        with st.spinner('Unificando dados dos arquivos...'):
            df_raw = process_files(uploaded_files)
        
        if not df_raw.empty:
            df_final = simplify_and_filter(df_raw)

            st.success(f"Sucesso! {len(df_final)} notas processadas.")
            st.dataframe(df_final)

            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_final.to_excel(writer, index=False, sheet_name='PortalServTax')
                workbook = writer.book
                worksheet = writer.sheets['PortalServTax']
                header_fmt = workbook.add_format({'bold': True, 'bg_color': '#FF69B4', 'font_color': 'white', 'border': 1})
                for i, col in enumerate(df_final.columns):
                    worksheet.write(0, i, col, header_fmt)
                    worksheet.set_column(i, i, 25)

            st.download_button(
                label="📥 Baixar Excel de Auditoria Unificado",
                data=output.getvalue(),
                file_name="portal_servtax_auditoria.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.warning("Nenhum dado encontrado.")

if __name__ == "__main__":
    main()
