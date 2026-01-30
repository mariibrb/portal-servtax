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

def simplify_columns(df):
    """Simplifica os nomes das colunas mantendo a integridade do DataFrame."""
    new_columns = {}
    for col in df.columns:
        if '_' in col:
            parts = col.split('_')
            # Tenta pegar o último termo
            simple_name = parts[-1]
            # Se for um nome muito comum ou curto, tenta pegar o pai + filho para evitar erro
            if simple_name.lower() in ['valor', 'codigo', 'numero', 'data'] and len(parts) > 1:
                simple_name = f"{parts[-2]}_{parts[-1]}"
            new_columns[col] = simple_name
        else:
            new_columns[col] = col
    return df.rename(columns=new_columns)

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
    st.subheader("Auditoria Fiscal de NFS-e (Consolidado)")

    uploaded_files = st.file_uploader("Arraste seus XMLs ou ZIPs aqui", type=["xml", "zip"], accept_multiple_files=True)

    if uploaded_files:
        with st.spinner('Extraindo dados...'):
            df_total = process_files(uploaded_files)
        
        if not df_total.empty:
            # Palavras-chave para auditoria
            keywords = [
                'Numero', 'Data', 'Cnpj', 'RazaoSocial', 'Valor', 'Iss', 'Pis', 
                'Cofins', 'Ir', 'Csll', 'Ibs', 'Cbs', 'Nbs', 'Cclass', 'Descricao', 'Chave'
            ]
            
            # Identifica quais colunas originais devem ser mantidas
            cols_to_keep = ['Arquivo_Origem']
            for col in df_total.columns:
                if any(key.lower() in col.lower() for key in keywords):
                    if col not in cols_to_keep:
                        cols_to_keep.append(col)
            
            # Filtra as colunas ORIGINAIS primeiro para evitar KeyError
            df_filtrado = df_total[cols_to_keep] if len(cols_to_keep) > 5 else df_total
            
            # AGORA sim simplifica os nomes das colunas para o usuário
            df_final = simplify_columns(df_filtrado)

            st.success(f"Concluído! {len(df_final)} notas e {len(df_final.columns)} colunas identificadas.")
            
            st.write("### Preview da Auditoria")
            st.dataframe(df_final.head(10))

            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_final.to_excel(writer, index=False, sheet_name='Auditoria_Fiscal')
                
                workbook = writer.book
                worksheet = writer.sheets['Auditoria_Fiscal']
                for i, col in enumerate(df_final.columns):
                    column_len = max(df_final[col].astype(str).str.len().max(), len(col)) + 2
                    worksheet.set_column(i, i, min(column_len, 40))

            st.download_button(
                label="📥 Baixar Excel Simplificado",
                data=output.getvalue(),
                file_name="portal_servtax_auditoria.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.warning("Nenhum XML válido encontrado.")

if __name__ == "__main__":
    main()
