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
    Motor de Equivalência de Alta Precisão: Mapeia caminhos exatos dos arquivos SP e Nacional.
    """
    final_df_data = {}
    if 'Arquivo_Origem' in df.columns:
        final_df_data['Arquivo'] = df['Arquivo_Origem']

    # MAPEAMENTO BASEADO NOS SEUS XMLS: 430510... (Nacional) e J9DL... (SP)
    mapping = {
        'Nota_Numero': ['nNFSe', 'NumeroNFe', 'nNF', 'numero'],
        'Data_Emissao': ['dhProc', 'DataEmissaoNFe', 'dhEmi', 'DataEmissao'],
        
        # PRESTADOR - Equivalências Diretas
        'Prestador_CNPJ': ['emit_CNPJ', 'CPFCNPJPrestador_CNPJ', 'CNPJPrestador', 'prestador_cnpj'],
        'Prestador_Razao': ['emit_xNome', 'RazaoSocialPrestador', 'prestador_razao', 'xNomePrestador'],
        
        # TOMADOR - O AJUSTE CRÍTICO AQUI
        'Tomador_CNPJ': ['toma_CNPJ', 'CPFCNPJTomador_CNPJ', 'CPFCNPJTomador_CPF', 'toma_CPF', 'CNPJTomador', 'CPFCNPJTomador_CpfCnpj_CNPJ'],
        'Tomador_Razao': ['toma_xNome', 'RazaoSocialTomador', 'dest_xNome', 'tomador_razao', 'xNomeTomador'],
        
        # VALORES
        'Vlr_Bruto': ['vServ', 'ValorServicos', 'valorbruto', 'v_serv', 'vNF'],
        
        # RETENÇÕES
        'ISS_Retido': ['vISSRet', 'ValorISS', 'iss_retido', 'ValorISS_Retido'],
        'PIS_Retido': ['vPIS', 'ValorPIS', 'pis_retido', 'vPIS_Ret'],
        'COFINS_Retido': ['vCOFINS', 'ValorCOFINS', 'cofins_retido', 'vCOFINS_Ret'],
        'IRRF_Retido': ['vIR', 'ValorIR', 'ir_retido', 'vIR_Ret'],
        'CSLL_Retido': ['vCSLL', 'ValorCSLL', 'csll_retido', 'vCSLL_Ret'],
        
        # DESCRIÇÃO
        'Servico_Descricao': ['xDescServ', 'Discriminacao', 'xServ', 'infCpl', 'xProd']
    }

    for friendly_name, radicals in mapping.items():
        found_series = None
        radicals_low = [r.lower() for r in radicals]
        
        for col in df.columns:
            col_low = col.lower()
            # Verifica se o final da coluna bate com o radical
            if any(col_low.endswith(rad) for rad in radicals_low):
                
                # Filtro de Contexto Rígido
                if 'prestador' in friendly_name.lower() and ('tomador' in col_low or 'toma' in col_low or 'dest' in col_low): 
                    continue
                if 'tomador' in friendly_name.lower() and ('prestador' in col_low or 'emit' in col_low): 
                    continue
                
                # Captura dados válidos
                current_col = df[col]
                if found_series is None or (isinstance(found_series, pd.Series) and found_series.isnull().all()):
                    found_series = current_col

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
    all_data = []
    for uploaded_file in uploaded_files:
        content = uploaded_file.read()
        if uploaded_file.name.lower().endswith('.xml'):
            all_data.append({'name': uploaded_file.name, 'content': content})
        elif uploaded_file.name.lower().endswith('.zip'):
            extract_xml_from_zip(content, all_data)
            
    final_rows = []
    for item in all_data:
        try:
            data_dict = xmltodict.parse(item['content'])
            # Processa se for lista de notas ou nota única
            if isinstance(data_dict, list):
                for sub in data_dict:
                    flat = flatten_dict(sub)
                    flat['Arquivo_Origem'] = item['name']
                    final_rows.append(flat)
            else:
                # Trata casos onde o root é diferente (NFe vs Retorno)
                root_key = list(data_dict.keys())[0]
                flat = flatten_dict(data_dict[root_key])
                flat['Arquivo_Origem'] = item['name']
                final_rows.append(flat)
        except: continue
    return pd.DataFrame(final_rows)

def main():
    st.title("📑 Portal ServTax")
    st.subheader("Auditoria Fiscal: Motor Híbrido SP & Nacional")

    uploaded_files = st.file_uploader("Upload de XML ou ZIP", type=["xml", "zip"], accept_multiple_files=True)

    if uploaded_files:
        with st.spinner('Consolidando mapeamentos fiscais...'):
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
                label="📥 Baixar Excel de Auditoria",
                data=output.getvalue(),
                file_name="portal_servtax_auditoria.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.warning("Nenhum dado válido encontrado.")

if __name__ == "__main__":
    main()
