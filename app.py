import streamlit as st
import pandas as pd
import xmltodict
import io
import zipfile

# Configuração da Página
st.set_page_config(page_title="Portal ServTax", layout="wide", page_icon="📑")

# Estilo Rihanna (Rosa e Branco)
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
                    items.append((f"{new_key}_{group_index}", item))
        else:
            items.append((new_key, v))
    return dict(items)

def simplify_and_filter(df):
    """
    Motor de Equivalência Múltipla: 
    Para cada coluna, tenta uma lista de tags possíveis (Nacional e SP).
    """
    final_df_data = {}
    if 'Arquivo_Origem' in df.columns:
        final_df_data['Arquivo'] = df['Arquivo_Origem']

    # DICIONÁRIO DE POSSIBILIDADES (O seu "SOMASES" de Tags)
    # Aqui estão as tags exatas encontradas nos seus XMLs da Amazon, Google, Shopee e Mercado Livre
    mapping = {
        'Nota_Numero': ['nNFSe', 'NumeroNFe', 'nNF', 'numero'],
        'Data_Emissao': ['dhProc', 'DataEmissaoNFe', 'dhEmi', 'dataemissao', 'DataEmissao'],
        
        # PRESTADOR (Tags de SP e do Bloco Nacional 'emit')
        'Prestador_CNPJ': ['emit_CNPJ', 'CPFCNPJPrestador_CNPJ', 'CNPJPrestador', 'prestador_cnpj'],
        'Prestador_Razao': ['emit_xNome', 'RazaoSocialPrestador', 'xNomePrestador', 'prestador_razao'],
        
        # TOMADOR (Tags de SP e do Bloco Nacional 'toma')
        'Tomador_CNPJ': ['toma_CNPJ', 'CPFCNPJTomador_CNPJ', 'CPFCNPJTomador_CPF', 'toma_CPF', 'dest_CNPJ'],
        'Tomador_Razao': ['toma_xNome', 'RazaoSocialTomador', 'dest_xNome', 'xNomeTomador'],
        
        # VALORES (vServ no Nacional / ValorServicos em SP)
        'Vlr_Bruto': ['vServ', 'ValorServicos', 'vNF', 'v_serv', 'vServPrest_vServ'],
        
        # IMPOSTOS E RETENÇÕES (Múltiplas nomenclaturas)
        'ISS_Valor': ['vISSRet', 'ValorISS', 'vISSQN', 'ValorISS_Retido', 'vISS'],
        'PIS_Retido': ['vPIS', 'ValorPIS', 'pis_retido', 'vPIS_Ret'],
        'COFINS_Retido': ['vCOFINS', 'ValorCOFINS', 'cofins_retido', 'vCOFINS_Ret'],
        'IRRF_Retido': ['vIR', 'ValorIR', 'ir_retido', 'vIR_Ret'],
        'CSLL_Retido': ['vCSLL', 'ValorCSLL', 'csll_retido', 'vCSLL_Ret'],
        
        # DESCRIÇÃO (xDescServ no Nacional / Discriminacao em SP)
        'Servico_Descricao': ['xDescServ', 'Discriminacao', 'xServ', 'infCpl', 'xProd']
    }

    for friendly_name, tags in mapping.items():
        found_series = None
        for col in df.columns:
            # Verifica se a coluna termina com a tag técnica (Case Insensitive)
            if any(col.lower().endswith(t.lower()) for t in tags):
                # Filtro Rígido: Não deixa Prestador ler tag de Tomador e vice-versa
                if 'Prestador' in friendly_name and ('Tomador' in col or 'toma' in col.lower() or 'dest' in col.lower()): continue
                if 'Tomador' in friendly_name and ('Prestador' in col or 'emit' in col.lower()): continue
                
                current_series = df[col]
                # Só aceita a coluna se ela tiver conteúdo (não for tudo nulo)
                if found_series is None or (isinstance(found_series, pd.Series) and found_series.isnull().all()):
                    found_series = current_series

        if found_series is not None:
            # Tratamento numérico para colunas financeiras
            if any(x in friendly_name for x in ['Vlr', 'ISS', 'PIS', 'COFINS', 'IR', 'CSLL']):
                final_df_data[friendly_name] = pd.to_numeric(found_series, errors='coerce').fillna(0.0)
            else:
                final_df_data[friendly_name] = found_series.fillna("Não Localizado")
        else:
            final_df_data[friendly_name] = 0.0 if any(x in friendly_name for x in ['Vlr', 'ISS', 'PIS', 'COFINS', 'IR', 'CSLL']) else "Não Localizado"

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
                for sub in data_dict:
                    flat = flatten_dict(sub)
                    flat['Arquivo_Origem'] = item['name']
                    final_rows.append(flat)
            else:
                flat = flatten_dict(data_dict)
                flat['Arquivo_Origem'] = item['name']
                final_rows.append(flat)
        except: continue
    return pd.DataFrame(final_rows)

def main():
    st.title("📑 Portal ServTax")
    st.subheader("Auditoria Fiscal: Detalhamento Linha a Linha (Tags Múltiplas)")

    uploaded_files = st.file_uploader("Upload de XML ou ZIP", type=["xml", "zip"], accept_multiple_files=True)

    if uploaded_files:
        with st.spinner('Processando equivalências de tags...'):
            df_raw = process_files(uploaded_files)
        
        if not df_raw.empty:
            df_final = simplify_and_filter(df_raw)

            st.success(f"Total de {len(df_final)} notas processadas com sucesso!")
            
            # Exibe o DataFrame completo na tela
            st.dataframe(df_final, use_container_width=True)

            # Exportação Excel
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_final.to_excel(writer, index=False, sheet_name='Auditoria_Detalhada')
                
                workbook = writer.book
                worksheet = writer.sheets['Auditoria_Detalhada']
                header_fmt = workbook.add_format({'bold': True, 'bg_color': '#FF69B4', 'font_color': 'white', 'border': 1})
                
                for i, col in enumerate(df_final.columns):
                    worksheet.write(0, i, col, header_fmt)
                    worksheet.set_column(i, i, 25)

            st.download_button(
                label="📥 Baixar Planilha de Auditoria Completa",
                data=output.getvalue(),
                file_name="auditoria_servtax_completa.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.warning("Nenhum dado encontrado nos arquivos.")

if __name__ == "__main__":
    main()
