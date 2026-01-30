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
    Motor de captura de alta sensibilidade com 'Plano B' para campos críticos.
    """
    final_df_data = {}
    if 'Arquivo_Origem' in df.columns:
        final_df_data['Arquivo'] = df['Arquivo_Origem']

    # Alvos principais com radicais expandidos
    targets = {
        'Nota_Numero': ['numero', 'nnfse', 'numnf', 'nfnr', 'notafiscal', 'identificacaonfse'],
        'Data_Emissao': ['dataemissao', 'dtemic', 'dtrem', 'dhemi', 'dtaemi', 'datahora', 'dh_emi', 'dt_emiss'],
        
        'Prestador_CNPJ': ['prestador_cnpj', 'prestador_cpfcnpj', 'prestador_cpf_cnpj', 'prestador_id'],
        'Prestador_Razao': ['prestador_razaosocial', 'prestador_xnome', 'prestador_razao', 'prestador_nome', 'prestador_xrazão'],
        
        'Tomador_CNPJ': ['tomador_cnpj', 'tomador_cpfcnpj', 'tomador_cpf_cnpj', 'tomador_id'],
        'Tomador_Razao': ['tomador_razaosocial', 'tomador_xnome', 'tomador_razao', 'tomador_nome', 'tomador_xrazão'],
        
        'Vlr_Bruto': ['valorservicos', 'vserv', 'vlrserv', 'valorbruto', 'vlrbruto', 'v_serv', 'v_servicos'],
        'ISS_Retido': ['issretido', 'vissret', 'iss_retido', 'valoriss', 'v_iss_ret'],
        'PIS_Retido': ['pisretido', 'vpisret', 'pis_retido', 'valorpis', 'v_pis_ret'],
        'COFINS_Retido': ['cofinsretido', 'vcofinsret', 'cofins_retido', 'valorcofins', 'v_cofins_ret'],
        'IRRF_Retido': ['valorir', 'vir', 'irrf_retido', 'virrf', 'v_ir_ret'],
        'CSLL_Retido': ['valorcsll', 'vcsll', 'csll_retido', 'v_csll_ret'],
        
        'Servico_Descricao': ['discriminacao', 'xserv', 'infadic', 'desc_serv', 'servico_discriminacao', 'txtservico']
    }

    for friendly_name, radicals in targets.items():
        found_series = None
        
        # PLANO A: Busca por radical e contexto (Prestador/Tomador)
        for col in df.columns:
            c_low = col.lower()
            if any(r in c_low for r in radicals):
                # Se for campo de Prestador, exige que a coluna tenha 'prestador'
                if 'prestador' in friendly_name.lower() and 'prestador' not in c_low: continue
                # Se for campo de Tomador, exige que a coluna tenha 'tomador'
                if 'tomador' in friendly_name.lower() and 'tomador' not in c_low: continue
                
                # Bloqueio de endereços
                if not any(x in c_low for x in ['endereco', 'logradouro', 'uf', 'cep', 'bairro']):
                    if found_series is None or found_series.isnull().all():
                        found_series = df[col]

        # PLANO B: Se CNPJ ou Razão ainda estão vazios, pega qualquer um que combine minimamente
        if (found_series is None or found_series.isnull().all()) and any(x in friendly_name for x in ['CNPJ', 'Razao']):
            for col in df.columns:
                c_low = col.lower()
                # Pega a última palavra da tag (ex: InfNfse_Tomador_CNPJ -> CNPJ)
                last_part = c_low.split('_')[-1]
                if any(r in last_part for r in ['cnpj', 'cpfcnpj', 'razao', 'nome']):
                    if 'prestador' in friendly_name.lower() and 'prestador' in c_low:
                        found_series = df[col]
                        break
                    if 'tomador' in friendly_name.lower() and 'tomador' in c_low:
                        found_series = df[col]
                        break

        if found_series is not None:
            if any(x in friendly_name for x in ['Vlr', 'ISS', 'PIS', 'COFINS', 'IR', 'CSLL']):
                final_df_data[friendly_name] = pd.to_numeric(found_series, errors='coerce').fillna(0.0)
            else:
                final_df_data[friendly_name] = found_series.fillna("Não Identificado")
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
            if isinstance(data_dict, list):
                for item in data_dict:
                    flat = flatten_dict(item)
                    flat['Arquivo_Origem'] = xml_item['name']
                    extracted_data.append(flat)
            else:
                flat_data = flatten_dict(data_dict)
                flat_data['Arquivo_Origem'] = xml_item['name']
                extracted_data.append(flat_data)
        except: continue
    return pd.DataFrame(extracted_data)

def main():
    st.title("📑 Portal ServTax")
    st.subheader("Auditoria Fiscal: Mapeamento de Alta Precisão")

    uploaded_files = st.file_uploader("Upload de XML ou ZIP", type=["xml", "zip"], accept_multiple_files=True)

    if uploaded_files:
        with st.spinner('Garimpando dados fiscais em todas as camadas...'):
            df_raw = process_files(uploaded_files)
        
        if not df_raw.empty:
            df_final = simplify_and_filter(df_raw)

            st.success(f"Notas processadas: {len(df_final)}")
            
            st.write("### Tabela de Auditoria")
            st.dataframe(df_final)

            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_final.to_excel(writer, index=False, sheet_name='PortalServTax')
                workbook = writer.book
                worksheet = writer.sheets['PortalServTax']
                header_fmt = workbook.add_format({'bold': True, 'bg_color': '#FF69B4', 'font_color': 'white', 'border': 1})
                for i, col in enumerate(df_final.columns):
                    worksheet.write(0, i, col, header_fmt)
                    worksheet.set_column(i, i, 22)

            st.download_button(
                label="📥 Baixar Excel Completo",
                data=output.getvalue(),
                file_name="portal_servtax_conferencia.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.warning("Nenhum arquivo XML válido detectado.")

if __name__ == "__main__":
    main()
