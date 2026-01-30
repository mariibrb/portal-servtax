import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
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

def get_tag_value(element, tag_name):
    """
    Busca uma tag ignorando namespaces (curinga {*}).
    """
    if element is None: return ""
    # Procura a tag em qualquer nível abaixo do elemento atual
    found = element.find(f".//{{*}}{tag_name}")
    if found is None:
        # Tenta busca simples caso não haja namespace
        found = element.find(f".//{tag_name}")
    return found.text.strip() if found is not None and found.text else ""

def process_xml_content(content, filename):
    try:
        root = ET.fromstring(content)
        
        # Identificação das Partes (Blocos Principais)
        # Nacional usa <emit> e <toma> / <tom>
        # SP usa <CPFCNPJPrestador> e <CPFCNPJTomador>
        
        row = {
            'Arquivo': filename,
            'Nota_Numero': get_tag_value(root, 'nNFSe') or get_tag_value(root, 'NumeroNFe') or get_tag_value(root, 'nNF'),
            'Data_Emissao': get_tag_value(root, 'dhProc') or get_tag_value(root, 'dhEmi') or get_tag_value(root, 'DataEmissaoNFe'),
            
            # PRESTADOR
            'Prestador_CNPJ': get_tag_value(root, 'emit') if get_tag_value(root, 'emit') else "", # Fallback
            'Prestador_Razao': get_tag_value(root, 'RazaoSocialPrestador') or ""
        }
        
        # Ajuste Fino para Prestador (CNPJ e Razão)
        emit_block = root.find(".//{* }emit") or root.find(".//emit")
        if emit_block is not None:
            row['Prestador_CNPJ'] = get_tag_value(emit_block, 'CNPJ') or get_tag_value(emit_block, 'CPF')
            row['Prestador_Razao'] = get_tag_value(emit_block, 'xNome')
        else:
            # Caso SP
            row['Prestador_CNPJ'] = get_tag_value(root, 'CPFCNPJPrestador') or get_tag_value(root, 'CNPJ')
            if not row['Prestador_Razao']:
                row['Prestador_Razao'] = get_tag_value(root, 'RazaoSocialPrestador')

        # TOMADOR
        toma_block = root.find(".//{* }toma") or root.find(".//toma") or root.find(".//{* }tom") or root.find(".//tom")
        if toma_block is not None:
            row['Tomador_CNPJ'] = get_tag_value(toma_block, 'CNPJ') or get_tag_value(toma_block, 'CPF')
            row['Tomador_Razao'] = get_tag_value(toma_block, 'xNome')
        else:
            # Caso SP
            row['Tomador_CNPJ'] = get_tag_value(root, 'CPFCNPJTomador') or get_tag_value(root, 'CNPJ')
            row['Tomador_Razao'] = get_tag_value(root, 'RazaoSocialTomador')

        # VALORES E IMPOSTOS
        row['Vlr_Bruto'] = get_tag_value(root, 'vServ') or get_tag_value(root, 'ValorServicos') or "0"
        row['ISS_Retido'] = get_tag_value(root, 'vISSRet') or get_tag_value(root, 'ValorISS') or "0"
        row['Descricao'] = get_tag_value(root, 'xDescServ') or get_tag_value(root, 'Discriminacao') or ""
        
        return row
    except:
        return None

def main():
    st.title("📑 Portal ServTax")
    st.subheader("Auditoria Fiscal: Mapeamento Universal (Nacional & SP)")

    uploaded_files = st.file_uploader("Upload de XML ou ZIP", type=["xml", "zip"], accept_multiple_files=True)

    if uploaded_files:
        data_rows = []
        for uploaded_file in uploaded_files:
            content = uploaded_file.read()
            if uploaded_file.name.lower().endswith('.zip'):
                with zipfile.ZipFile(io.BytesIO(content)) as z:
                    for xml_name in z.namelist():
                        if xml_name.lower().endswith('.xml'):
                            res = process_xml_content(z.read(xml_name), xml_name)
                            if res: data_rows.append(res)
            else:
                res = process_xml_content(content, uploaded_file.name)
                if res: data_rows.append(res)

        if data_rows:
            df = pd.DataFrame(data_rows)
            
            # Limpeza de colunas numéricas
            for col in ['Vlr_Bruto', 'ISS_Retido']:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)

            st.success(f"Notas processadas: {len(df)}")
            st.dataframe(df)

            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='Auditoria')
                workbook = writer.book
                worksheet = writer.sheets['Auditoria']
                header_fmt = workbook.add_format({'bold': True, 'bg_color': '#FF69B4', 'font_color': 'white', 'border': 1})
                for i, col in enumerate(df.columns):
                    worksheet.write(0, i, col, header_fmt)
                    worksheet.set_column(i, i, 20)

            st.download_button(
                label="📥 Baixar Planilha de Auditoria",
                data=output.getvalue(),
                file_name="portal_servtax_auditoria.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.error("Nenhum dado capturado. Verifique se os arquivos são XMLs de notas válidos.")

if __name__ == "__main__":
    main()
