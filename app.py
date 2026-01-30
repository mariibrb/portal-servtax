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
    Filtra colunas com mapeamento expandido baseado em padrões reais (SP, Guarulhos, Nacional).
    """
    mapping = {
        'Nota_Numero': ['numero', 'nfnr', 'numnf', 'nnfse', 'nrnotafiscal'],
        'Data_Emissao': ['dataemissao', 'dtemic', 'dtrem', 'dtaemi', 'dh_emi'],
        'Prestador_CNPJ': ['prestador_cnpj', 'prestador_cpfcnpj', 'prestador_identificacao', 'prestador_id'],
        'Prestador_Razao': ['prestador_razãosocial', 'prestador_xnome', 'prestador_razão', 'prestador_nome'],
        'Tomador_CNPJ': ['tomador_cnpj', 'tomador_cpfcnpj', 'tomador_identificacao', 'tomador_id'],
        'Tomador_Razao': ['tomador_razãosocial', 'tomador_xnome', 'tomador_razão', 'tomador_nome'],
        'Vlr_Bruto': ['valorservicos', 'vserv', 'vlrserv', 'valorbruto', 'v_serv'],
        'Vlr_Liquido': ['valorliquido', 'vliq', 'vlrliq', 'v_liq'],
        # ISS
        'ISS_Total': ['valoriss', 'viss', 'v_iss'],
        'ISS_Retido': ['issretido', 'vissret', 'iss_retido', 'v_iss_ret'],
        # PIS
        'PIS_Total': ['valorpis', 'vpis', 'v_pis'],
        'PIS_Retido': ['pisretido', 'vpisret', 'v_pis_ret'],
        # COFINS
        'COFINS_Total': ['valorcofins', 'vcofins', 'v_cofins'],
        'COFINS_Retido': ['cofinsretido', 'vcofinsret', 'v_cofins_ret'],
        # IRRF
        'IRRF_Retido': ['valorir', 'vir', 'irrf_retido', 'virrf', 'v_ir'],
        # CSLL
        'CSLL_Retido': ['valorcsll', 'vcsll', 'csll_retido', 'v_csll'],
        # INSS
        'INSS_Retido': ['valorinss', 'vinss', 'v_inss'],
        # Reforma Tributária
        'IBS': ['ibs_vlr', 'ibs_valor', 'v_ibs'],
        'CBS': ['cbs_vlr', 'cbs_valor', 'v_cbs'],
        'Servico_Descricao': ['discriminacao', 'xserv', 'infadic', 'desc_serv']
    }

    final_df_data = {}
    if 'Arquivo_Origem' in df.columns:
        final_df_data['Arquivo'] = df['Arquivo_Origem']

    for friendly_name, radicals in mapping.items():
        found_col = None
        # Procura a melhor coluna para o radical, evitando endereços
        for col in df.columns:
            col_lower = col.lower()
            if any(rad in col_lower for rad in radicals):
                if not any(x in col_lower for x in ['endereco', 'logradouro', 'uf', 'cep', 'bairro', 'complemento']):
                    found_col = col
                    break
        
        if found_col:
            # Converte para numérico se for valor de imposto
            if any(x in friendly_name for x in ['Vlr', 'ISS', 'PIS', 'COFINS', 'IR', 'CSLL', 'IBS', 'CBS', 'INSS']):
                final_df_data[friendly_name] = pd.to_numeric(df[found_col], errors='coerce').fillna(0.0)
            else:
                final_df_data[friendly_name] = df[found_col]
        else:
            final_df_data[friendly_name] = 0.0 if any(x in friendly_name for x in ['Vlr', 'ISS', 'PIS', 'COFINS', 'IR', 'CSLL', 'IBS', 'CBS', 'INSS']) else "Não encontrado"

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
    st.subheader("Auditoria Fiscal de Alta Precisão (Retidos e Totais)")

    uploaded_files = st.file_uploader("Upload de XML ou ZIP", type=["xml", "zip"], accept_multiple_files=True)

    if uploaded_files:
        with st.spinner('Realizando mapeamento profundo de tags...'):
            df_raw = process_files(uploaded_files)
        
        if not df_raw.empty:
            df_final = simplify_and_filter(df_raw)

            st.success(f"Concluído: {len(df_final)} notas mapeadas.")
            
            st.write("### Conferência de Impostos")
            st.dataframe(df_final)

            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_final.to_excel(writer, index=False, sheet_name='Auditoria_Fiscal')
                
                workbook = writer.book
                worksheet = writer.sheets['Auditoria_Fiscal']
                
                # Formatação de Dinheiro para as colunas de valores
                money_fmt = workbook.add_format({'num_format': '#,##0.00'})
                header_fmt = workbook.add_format({'bold': True, 'bg_color': '#FF69B4', 'font_color': 'white'})

                for i, col in enumerate(df_final.columns):
                    worksheet.write(0, i, col, header_fmt)
                    if any(x in col for x in ['Vlr', 'ISS', 'PIS', 'COFINS', 'IR', 'CSLL', 'IBS', 'CBS', 'INSS']):
                        worksheet.set_column(i, i, 15, money_fmt)
                    else:
                        worksheet.set_column(i, i, 25)

            st.download_button(
                label="📥 Baixar Excel de Auditoria Completo",
                data=output.getvalue(),
                file_name="auditoria_fiscal_completa.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.warning("Nenhum arquivo XML válido encontrado.")

if __name__ == "__main__":
    main()
