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
    Filtra apenas as colunas essenciais de auditoria e simplifica os nomes
    evitando tags de endereço e burocracias.
    """
    # 1. Mapeamento de tags essenciais (Alvos principais)
    targets = {
        'Numero': 'Nota_Numero',
        'DataEmissao': 'Data_Emissao',
        'CpfCnpj': 'CNPJ', # Será tratado para Prestador/Tomador
        'RazaoSocial': 'Razao_Social',
        'ValorServicos': 'Vlr_Bruto',
        'ValorLiquido': 'Vlr_Liquido',
        'ValorIss': 'ISS',
        'ValorPis': 'PIS',
        'ValorCofins': 'COFINS',
        'ValorIr': 'IRRF',
        'ValorCsll': 'CSLL',
        'OutrasRetencoes': 'Outras_Ret',
        'IBS_Valor': 'IBS',
        'CBS_Valor': 'CBS',
        'NBS': 'NBS',
        'Cclass': 'Cclass',
        'Discriminacao': 'Servico_Descricao'
    }

    final_data = {}
    cols = df.columns
    
    # Sempre incluir a origem
    if 'Arquivo_Origem' in cols:
        final_data['Arquivo'] = df['Arquivo_Origem']

    for orig_col in cols:
        for tag, simple_name in targets.items():
            if tag.lower() in orig_col.lower():
                # Bloqueio de endereços e IBGE
                if any(x in orig_col.lower() for x in ['endereco', 'logradouro', 'complemento', 'bairro', 'ibge', 'uf', 'cep']):
                    continue
                
                # Identifica se é Prestador ou Tomador para o CNPJ e Razão
                name = simple_name
                if 'prestador' in orig_col.lower():
                    name = f"Prestador_{simple_name}"
                elif 'tomador' in orig_col.lower():
                    name = f"Tomador_{simple_name}"
                
                final_data[name] = df[orig_col]

    return pd.DataFrame(final_data)

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
    st.subheader("Auditoria Fiscal Direta (Sem Burocracia)")

    uploaded_files = st.file_uploader("Arraste seus XMLs ou ZIPs aqui", type=["xml", "zip"], accept_multiple_files=True)

    if uploaded_files:
        with st.spinner('Filtrando apenas o essencial...'):
            df_raw = process_files(uploaded_files)
        
        if not df_raw.empty:
            # Aplica o filtro rígido de colunas
            df_final = simplify_and_filter(df_raw)

            st.success(f"Notas processadas: {len(df_final)}. Colunas reduzidas para o essencial.")
            
            st.write("### Tabela de Conferência")
            st.dataframe(df_final)

            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_final.to_excel(writer, index=False, sheet_name='Auditoria_Limpa')
                
                workbook = writer.book
                worksheet = writer.sheets['Auditoria_Limpa']
                for i, col in enumerate(df_final.columns):
                    column_len = max(df_final[col].astype(str).str.len().max(), len(col)) + 2
                    worksheet.set_column(i, i, min(column_len, 50))

            st.download_button(
                label="📥 Baixar Excel de Auditoria",
                data=output.getvalue(),
                file_name="auditoria_servtax_objetivo.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.warning("Nenhum dado válido encontrado.")

if __name__ == "__main__":
    main()
