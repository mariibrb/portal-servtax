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
    .instrucoes { background-color: #FFF0F5; border-left: 5px solid #FF69B4; padding: 15px; border-radius: 5px; margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

def get_xml_value(root, tags):
    """
    Busca em Cascata com XPath: tenta cada tag da lista em qualquer nível do XML.
    Ignora namespaces para garantir leitura universal.
    """
    for tag in tags:
        element = root.find(f".//{{*}}{tag}")
        if element is None:
            element = root.find(f".//{tag}")
        
        if element is not None and element.text:
            return element.text.strip()
    return "0.00" if any(x in tag.lower() for x in ['vlr', 'valor', 'iss', 'pis', 'cofins', 'ir', 'csll', 'liquido', 'trib']) else ""

def process_xml_file(content, filename):
    try:
        tree = ET.parse(io.BytesIO(content))
        root = tree.getroot()
        
        # FLAGS DE VERIFICAÇÃO
        iss_retido_flag = get_xml_value(root, ['ISSRetido']).lower()
        tp_ret_flag = get_xml_value(root, ['tpRetISSQN'])
        
        # MAPEAMENTO DE POSSIBILIDADES
        row = {
            'Arquivo': filename,
            'Nota_Numero': get_xml_value(root, ['nNFSe', 'NumeroNFe', 'nNF', 'numero', 'Numero']),
            'Data_Emissao': get_xml_value(root, ['dhProc', 'dhEmi', 'DataEmissaoNFe', 'DataEmissao', 'dtEmi']),
            
            # PRESTADOR
            'Prestador_CNPJ': get_xml_value(root, ['emit/CNPJ', 'CPFCNPJPrestador/CNPJ', 'CNPJPrestador', 'emit_CNPJ', 'CPFCNPJPrestador/CPF', 'CNPJ']),
            'Prestador_Razao': get_xml_value(root, ['emit/xNome', 'RazaoSocialPrestador', 'xNomePrestador', 'emit_xNome', 'RazaoSocial', 'xNome']),
            
            # TOMADOR
            'Tomador_CNPJ': get_xml_value(root, ['toma/CNPJ', 'CPFCNPJTomador/CNPJ', 'CPFCNPJTomador/CPF', 'dest/CNPJ', 'CNPJTomador', 'toma/CPF', 'tom/CNPJ', 'CNPJ']),
            'Tomador_Razao': get_xml_value(root, ['toma/xNome', 'RazaoSocialTomador', 'dest/xNome', 'xNomeTomador', 'RazaoSocialTomador', 'tom/xNome', 'xNome']),
            
            # VALORES TOTAIS
            'Vlr_Bruto': get_xml_value(root, ['vServ', 'ValorServicos', 'vNF', 'vServPrest/vServ', 'ValorTotal']),
            'Vlr_Liquido': get_xml_value(root, ['vLiq', 'ValorLiquidoNFe', 'vLiqNFSe', 'vLiquido', 'vServPrest/vLiq']),
            
            # ISS PRÓPRIO
            'ISS_Valor': get_xml_value(root, ['vISS', 'ValorISS', 'vISSQN', 'iss/vISS']),
            
            # RETENÇÕES IMPOSTOS FEDERAIS
            'Ret_PIS': get_xml_value(root, ['vPIS', 'ValorPIS', 'vPIS_Ret', 'PISRetido', 'vRetPIS']),
            'Ret_COFINS': get_xml_value(root, ['vCOFINS', 'ValorCOFINS', 'vCOFINS_Ret', 'COFINSRetido', 'vRetCOFINS']),
            'Ret_CSLL': get_xml_value(root, ['vCSLL', 'ValorCSLL', 'vCSLL_Ret', 'CSLLRetido', 'vRetCSLL']),
            'Ret_IRRF': get_xml_value(root, ['vIR', 'ValorIR', 'vIR_Ret', 'IRRetido', 'vRetIR', 'vIRRF']),
            
            # Descrição
            'Descricao': get_xml_value(root, ['CodigoServico', 'itemServico', 'cServ', 'xDescServ', 'Discriminacao', 'xServ', 'infCpl', 'xProd'])
        }

        # LÓGICA DE BLINDAGEM DE RETENÇÃO ISS
        if tp_ret_flag == '2' or iss_retido_flag == 'true':
             row['Ret_ISS'] = get_xml_value(root, ['vTotTribMun', 'vISSRetido', 'ValorISS_Retido', 'vRetISS', 'vISSRet', 'iss/vRet'])
        elif iss_retido_flag == 'false' or tp_ret_flag == '1':
             row['Ret_ISS'] = "0.00"
        else:
             row['Ret_ISS'] = get_xml_value(root, ['vTotTribMun', 'vISSRetido', 'ValorISS_Retido', 'vRetISS', 'vISSRet', 'iss/vRet'])

        return row
    except:
        return None

def main():
    st.title("📑 Portal ServTax")
    
    # --- MANUAL DE INSTRUÇÕES E OBJETIVOS ---
    with st.expander("📖 Manual de Instruções e Objetivos (Clique para expandir)", expanded=True):
        st.markdown("""
        <div class="instrucoes">
            <h3>🎯 O que esta ferramenta faz?</h3>
            <p>O <b>Portal ServTax</b> realiza a leitura universal de arquivos XML de Notas Fiscais de Serviço (NFSe), 
            identificando automaticamente dados de prestadores, tomadores, valores brutos, líquidos e retenções tributárias 
            (ISS, PIS, COFINS, CSLL e IRRF), tanto no padrão de São Paulo quanto no Padrão Nacional.</p>
            
            <h3>🚀 Passo a Passo:</h3>
            <ol>
                <li><b>Upload:</b> Clique no botão abaixo ou arraste seus arquivos <b>.XML</b> ou <b>.ZIP</b> (contendo XMLs).</li>
                <li><b>Processamento:</b> A ferramenta lerá cada arquivo em cascata para encontrar as tags corretas de cada município.</li>
                <li><b>Diagnóstico:</b> Verifique a coluna final de <b>Diagnóstico</b>:
                    <ul>
                        <li>✅ : O valor bruto e líquido batem (não há retenções aparentes).</li>
                        <li>⚠️ : Diferença detectada! Avalie as colunas de retenção para escrituração.</li>
                    </ul>
                </li>
                <li><b>Exportação:</b> Baixe o resultado em Excel para seguir com sua auditoria fiscal.</li>
            </ol>
        </div>
        """, unsafe_allow_html=True)

    st.subheader("Auditoria Fiscal: Mapeamento Universal")

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
            
            # Conversão Numérica
            cols_fin = ['Vlr_Bruto', 'Vlr_Liquido', 'ISS_Valor', 'Ret_ISS', 'Ret_PIS', 'Ret_COFINS', 'Ret_CSLL', 'Ret_IRRF']
            for col in cols_fin:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)

            # DIAGNÓSTICO
            def gerar_diagnostico(row):
                if abs(row['Vlr_Bruto'] - row['Vlr_Liquido']) > 0.01:
                    return "⚠️ ATENÇÃO: Divergência Detectada! Verificar Retenções."
                return "✅"
            
            df['Diagnostico'] = df.apply(gerar_diagnostico, axis=1)

            # AJUSTE DA ORDEM DAS COLUNAS: Ret_ISS logo após ISS_Valor
            cols = list(df.columns)
            if 'Ret_ISS' in cols and 'ISS_Valor' in cols:
                cols.insert(cols.index('ISS_Valor') + 1, cols.pop(cols.index('Ret_ISS')))
                df = df[cols]

            st.success(f"Notas processadas com sucesso: {len(df)}")
            st.dataframe(df)

            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='PortalServTax')
                workbook = writer.book
                worksheet = writer.sheets['PortalServTax']
                header_fmt = workbook.add_format({'bold': True, 'bg_color': '#FF69B4', 'font_color': 'white', 'border': 1})
                num_fmt = workbook.add_format({'num_format': '#,##0.00'})
                
                for i, col in enumerate(df.columns):
                    worksheet.write(0, i, col, header_fmt)
                    if col in cols_fin:
                        worksheet.set_column(i, i, 18, num_fmt)
                    elif col == 'Diagnostico':
                        worksheet.set_column(i, i, 45)
                    else:
                        worksheet.set_column(i, i, 22)

            st.download_button(
                label="📥 Baixar Planilha de Auditoria",
                data=output.getvalue(),
                file_name="portal_servtax_auditoria.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.error("Nenhum dado capturado nos ficheiros.")

if __name__ == "__main__":
    main()
