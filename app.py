import streamlit as st
import pandas as pd
import xmltodict
import io
import zipfile

# Configuração da Página
st.set_page_config(page_title="Portal ServTax", layout="wide", page_icon="📑")

# Estilo Visual (Rihanna) - Rosa e Branco
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;700&family=Plus+Jakarta+Sans:wght@400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Plus Jakarta Sans', sans-serif; }
    h1, h2, h3 { font-family: 'Montserrat', sans-serif; color: #FF69B4; }
    .stButton>button { background-color: #FF69B4; color: white; border-radius: 10px; border: none; font-weight: bold; width: 100%; }
    .stButton>button:hover { background-color: #FFDEEF; color: #FF69B4; border: 1px solid #FF69B4; }
    [data-testid="stFileUploadDropzone"] { border: 2px dashed #FF69B4; background-color: #FFDEEF; }
    </style>
    """, unsafe_allow_html=True)

def flatten_dict(d, parent_key='', sep='_'):
    """Transforma o XML aninhado em colunas lineares."""
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
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

def extract_xml_from_zip(zip_data, extracted_list):
    """Extração recursiva de ZIPs dentro de ZIPs."""
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
            flat_data['arquivo_origem'] = xml_item['name']
            extracted_data.append(flat_data)
        except:
            continue
    return pd.DataFrame(extracted_data)

def main():
    st.title("📑 Portal ServTax")
    st.subheader("Auditoria Fiscal: Conferência de Retenções e Reforma Tributária")

    st.markdown("""
    Este módulo realiza a leitura completa de **todas as tags** e exporta as colunas essenciais para conferência de 
    escrituração (PIS, COFINS, CSLL, IR, ISS, além de IBS e CBS).
    """)

    uploaded_files = st.file_uploader("Selecione os arquivos XML ou ZIP", type=["xml", "zip"], accept_multiple_files=True)

    if uploaded_files:
        with st.spinner('Minerando dados fiscais...'):
            df_total = process_files(uploaded_files)
        
        if not df_total.empty:
            # Lista mestre para auditoria (ordenada logicamente)
            colunas_auditoria = [
                'arquivo_origem', 'Numero', 'DataEmissao', 'ChaveAcesso',
                'Prestador_CpfCnpj', 'Prestador_RazaoSocial',
                'Tomador_CpfCnpj', 'Tomador_RazaoSocial',
                'Valores_ValorServicos', 'Valores_ValorLiquidoNfse',
                'Valores_ValorIss', 'Valores_IssRetido', 'Valores_Aliquota',
                'Valores_ValorPis', 'Valores_ValorCofins', 'Valores_ValorIr', 'Valores_ValorCsll',
                'IBS_Valor', 'CBS_Valor', 'IBS_Aliquota', 'CBS_Aliquota', 
                'NBS', 'Cclass', 'ItemListaServico', 'Discriminacao'
            ]
            
            # Garante que apenas as colunas que existem no XML apareçam
            colunas_finais = [c for c in colunas_auditoria if c in df_total.columns]
            df_final = df_total[colunas_finais]

            st.success(f"Notas processadas para auditoria: {len(df_final)}")
            
            # Preview rápido
            st.dataframe(df_final.head(10))

            # Preparação do Excel
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_final.to_excel(writer, index=False, sheet_name='Auditoria_Fiscal')
                
                # Ajuste automático de colunas no Excel
                workbook = writer.book
                worksheet = writer.sheets['Auditoria_Fiscal']
                for i, col in enumerate(df_final.columns):
                    column_len = max(df_final[col].astype(str).str.len().max(), len(col)) + 2
                    worksheet.set_column(i, i, column_len)

            st.download_button(
                label="📥 Baixar Planilha para Conferência",
                data=output.getvalue(),
                file_name="conferencia_fiscal_servtax.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.warning("Nenhum dado XML foi encontrado nos arquivos enviados.")

if __name__ == "__main__":
    main()
