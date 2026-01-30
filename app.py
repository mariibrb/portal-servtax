import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
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

def get_xml_value(root, tags):
    """
    Busca profunda em cascata: tenta cada tag da lista até encontrar o valor.
    """
    for tag in tags:
        # Busca ignorando namespaces para compatibilidade universal
        element = root.find(f".//{{*}}{tag}")
        if element is None:
            element = root.find(f".//{tag}")
        
        if element is not None and element.text:
            return element.text.strip()
    return ""

def process_xml_file(content, filename):
    try:
        tree = ET.parse(io.BytesIO(content))
        root = tree.getroot()
        
        # MAPEAMENTO DE POSSIBILIDADES (Ajuste Fino SP & Nacional)
        row = {
            'Arquivo': filename,
            'Municipio': get_xml_value(root, ['xLocEmi', 'NomeCidade', 'Cidade', 'xMun']),
            
            # Número da Nota
            'Nota_Numero': get_xml_value(root, ['nNFSe', 'NumeroNFe', 'nNF', 'numero', 'Numero']),
            
            # Data de Emissão
            'Data_Emissao': get_xml_value(root, ['dhProc', 'dhEmi', 'DataEmissaoNFe', 'DataEmissao', 'dtEmi']),
            
            # PRESTADOR (Ajuste Fino: RazaoSocialPrestador para SP e xNome para Nacional)
            'Prestador_CNPJ': get_xml_value(root, ['emit/CNPJ', 'CPFCNPJPrestador/CNPJ', 'CNPJPrestador', 'emit_CNPJ']),
            'Prestador_Razao': get_xml_value(root, ['RazaoSocialPrestador', 'emit/xNome', 'xNomePrestador', 'emit_xNome', 'RazaoSocial']),
            
            # TOMADOR
            'Tomador_CNPJ': get_xml_value(root, ['toma/CNPJ', 'CPFCNPJTomador/CNPJ', 'CPFCNPJTomador/CPF', 'dest/CNPJ', 'CNPJTomador']),
            'Tomador_Razao': get_xml_value(root, ['toma/xNome', 'RazaoSocialTomador', 'dest/xNome', 'xNomeTomador', 'RazaoSocialTomador']),
            
            # Valores e Impostos
            'Vlr_Bruto': get_xml_value(root, ['vServ', 'ValorServicos', 'vNF', 'vServPrest/vServ', 'ValorTotal']),
            'ISS_Retido': get_xml_value(root, ['vISSRet', 'ValorISS', 'vISSQN', 'ValorISS_Retido', 'ISSRetido']),
            
            # Impostos Federais
            'PIS': get_xml_value(root, ['vPIS', 'ValorPIS', 'vPIS_Ret', 'PISRetido']),
            'COFINS': get_xml_value(root, ['vCOFINS', 'ValorCOFINS', 'vCOFINS_Ret', 'COFINSRetido']),
            
            # Descrição do Serviço
            'Descricao': get_xml_value(root, ['xDescServ', 'Discriminacao', 'xServ', 'infCpl', 'xProd'])
        }
        return row
    except:
        return None

def main():
    st.title("📑 Portal ServTax")
    st.subheader("Auditoria Fiscal Multi-Prefeituras (Versão Final Ajustada)")

    uploaded_files = st.file_uploader("Upload de XML ou ZIP", type=["xml", "zip"], accept_multiple_files=True)

    if uploaded_files:
        data_rows = []
        for uploaded_file in uploaded_files:
            if uploaded_file.name.endswith('.zip'):
                with zipfile.ZipFile(uploaded_file) as z:
                    for xml_name in z.namelist():
                        if xml_name.endswith('.xml'):
                            res = process_xml_file(z.read(xml_name), xml_name)
                            if res: data_rows.append(res)
            else:
                res = process_xml_file(uploaded_file.read(), uploaded_file.name)
                if res: data_rows.append(res)

        if data_rows:
            df = pd.DataFrame(data_rows)
            
            # Conversão de valores financeiros para cálculo e exibição correta
            cols_fin = ['Vlr_Bruto', 'ISS_Retido', 'PIS', 'COFINS']
            for col in cols_fin:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)

            st.success(f"Notas processadas com sucesso: {len(df)}")
            st.dataframe(df)

            # Exportação Excel
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='PortalServTax')
                workbook = writer.book
                worksheet = writer.sheets['PortalServTax']
                header_fmt = workbook.add_format({'bold': True, 'bg_color': '#FF69B4', 'font_color': 'white', 'border': 1})
                for i, col in enumerate(df.columns):
                    worksheet.write(0, i, col, header_fmt)
                    worksheet.set_column(i, i, 22)

            st.download_button(
                label="📥 Baixar Planilha de Auditoria Final",
                data=output.getvalue(),
                file_name="portal_servtax_auditoria.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

if __name__ == "__main__":
    main()
