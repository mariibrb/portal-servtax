import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
import io
import zipfile

# --- CONFIGURAÇÃO E INTERFACE ---
st.set_page_config(
    page_title="Portal Tax NFS-e", 
    page_icon="📑", 
    layout="wide"
)

# --- ESTILO SENTINELA DINÂMICO ---
def aplicar_estilo_sentinela_zonas():
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;800&family=Plus+Jakarta+Sans:wght@400;700&display=swap');

        header, [data-testid="stHeader"] { display: none !important; }
        .stApp { transition: background 0.8s ease-in-out !important; }

        div.stButton > button {
            color: #6C757D !important; 
            background-color: #FFFFFF !important; 
            border: 1px solid #DEE2E6 !important;
            border-radius: 15px !important;
            font-family: 'Montserrat', sans-serif !important;
            font-weight: 800 !important;
            height: 75px !important;
            text-transform: uppercase;
            opacity: 0.8;
            transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275) !important;
        }

        div.stButton > button:hover {
            transform: translateY(-5px) !important;
            opacity: 1 !important;
            box-shadow: 0 10px 20px rgba(0,0,0,0.1) !important;
        }

        .stApp { 
            background: radial-gradient(circle at top right, #FFDEEF 0%, #F8F9FA 100%) !important; 
        }

        [data-testid="stFileUploader"] { 
            border: 2px dashed #FF69B4 !important; 
            border-radius: 20px !important;
            background: #FFFFFF !important;
            padding: 30px !important;
        }

        [data-testid="stFileUploader"] section button, 
        div.stDownloadButton > button {
            background-color: #FF69B4 !important; 
            color: white !important; 
            border: 3px solid #FFFFFF !important;
            font-weight: 700 !important;
            border-radius: 15px !important;
            box-shadow: 0 0 15px rgba(255, 105, 180, 0.4) !important;
        }

        h1 {
            font-family: 'Montserrat', sans-serif;
            font-weight: 800;
            color: #FF69B4 !important;
            text-align: center;
            margin-bottom: 20px;
        }
        
        .instrucoes-card {
            background-color: rgba(255, 255, 255, 0.7);
            border-radius: 15px;
            padding: 20px;
            border-left: 5px solid #FF69B4;
            margin-bottom: 20px;
            height: 100%;
        }
        </style>
    """, unsafe_allow_html=True)

aplicar_estilo_sentinela_zonas()

# --- LÓGICA DE PROCESSAMENTO ---
def get_xml_value(root, tags):
    for tag in tags:
        # Busca recursiva em qualquer nível do XML para capturar tags dentro de blocos como <piscofins>
        element = root.find(f".//{{*}}{tag}")
        if element is None:
            element = root.find(f".//{tag}")
        if element is not None and element.text:
            return element.text.strip()
    # Se não encontrar nada, retorna 0.00 para campos numéricos identificados por prefixos ou palavras-chave
    return "0.00" if any(x in str(tags).lower() for x in ['vlr', 'valor', 'iss', 'pis', 'cofins', 'ir', 'csll', 'liq', 'trib', 'v_']) else ""

def process_xml_file(content, filename):
    try:
        tree = ET.parse(io.BytesIO(content))
        root = tree.getroot()
        iss_retido_flag = get_xml_value(root, ['ISSRetido']).lower()
        tp_ret_flag = get_xml_value(root, ['tpRetISSQN'])
        
        row = {
            'Arquivo': filename,
            'Nota_Numero': get_xml_value(root, ['nNFSe', 'NumeroNFe', 'nNF', 'numero', 'Numero']),
            'Data_Emissao': get_xml_value(root, ['dhProc', 'dhEmi', 'DataEmissaoNFe', 'DataEmissao', 'dtEmi']),
            'Prestador_CNPJ': get_xml_value(root, ['emit/CNPJ', 'CPFCNPJPrestador/CNPJ', 'CNPJPrestador', 'emit_CNPJ', 'CPFCNPJPrestador/CPF', 'CNPJ']),
            'Prestador_Razao': get_xml_value(root, ['emit/xNome', 'RazaoSocialPrestador', 'xNomePrestador', 'emit_xNome', 'RazaoSocial', 'xNome']),
            'Tomador_CNPJ': get_xml_value(root, ['toma/CNPJ', 'CPFCNPJTomador/CNPJ', 'CPFCNPJTomador/CPF', 'dest/CNPJ', 'CNPJTomador', 'toma/CPF', 'tom/CNPJ', 'CNPJ']),
            'Tomador_Razao': get_xml_value(root, ['toma/xNome', 'RazaoSocialTomador', 'dest/xNome', 'xNomeTomador', 'RazaoSocialTomador', 'tom/xNome', 'xNome']),
            'Vlr_Bruto': get_xml_value(root, ['vServ', 'ValorServicos', 'vNF', 'vServPrest/vServ', 'ValorTotal']),
            'Vlr_Liquido': get_xml_value(root, ['vLiq', 'ValorLiquidoNFe', 'vLiqNFSe', 'vLiquido', 'vServPrest/vLiq']),
            'ISS_Valor': get_xml_value(root, ['vISS', 'ValorISS', 'vISSQN', 'iss/vISS']),
            'Ret_PIS': get_xml_value(root, ['vPis', 'vPIS', 'ValorPIS', 'vPIS_Ret', 'PISRetido', 'vRetPIS']),
            'Ret_COFINS': get_xml_value(root, ['vCofins', 'vCOFINS', 'ValorCOFINS', 'vCOFINS_Ret', 'COFINSRetido', 'vRetCOFINS']),
            'Ret_CSLL': get_xml_value(root, ['vRetCSLL', 'vCSLL', 'ValorCSLL', 'vCSLL_Ret', 'CSLLRetido', 'vRetCSLL']),
            'Ret_IRRF': get_xml_value(root, ['vIR', 'ValorIR', 'vIR_Ret', 'IRRetido', 'vRetIR', 'vIRRF']),
            'Descricao': get_xml_value(root, ['CodigoServico', 'itemServico', 'cServ', 'xDescServ', 'Discriminacao', 'xServ', 'infCpl', 'xProd'])
        }

        if tp_ret_flag == '2' or iss_retido_flag == 'true':
             row['Ret_ISS'] = get_xml_value(root, ['vTotTribMun', 'vISSRetido', 'ValorISS_Retido', 'vRetISS', 'vISSRet', 'iss/vRet'])
        elif iss_retido_flag == 'false' or tp_ret_flag == '1':
             row['Ret_ISS'] = "0.00"
        else:
             row['Ret_ISS'] = get_xml_value(root, ['vTotTribMun', 'vISSRetido', 'ValorISS_Retido', 'vRetISS', 'vISSRet', 'iss/vRet'])
        return row
    except:
        return None

# --- ÁREA VISUAL ---
st.title("PORTAL TAX NFS-e - AUDITORIA FISCAL")

col1, col2 = st.columns(2)

with col1:
    st.markdown("""
    <div class="instrucoes-card">
        <h3>📖 Passo a Passo</h3>
        <ol>
            <li><b>Upload:</b> Arraste arquivos <b>.XML</b> ou <b>.ZIP</b> abaixo.</li>
            <li><b>Ação:</b> Clique em <b>"INICIAR AUDITORIA"</b>.</li>
            <li><b>Conferência:</b> Analise o <b>Diagnóstico</b> detalhado de divergências.</li>
            <li><b>Saída:</b> Baixe o Excel final para auditoria.</li>
        </ol>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
    <div class="instrucoes-card">
        <h3>📊 O que será obtido?</h3>
        <ul>
            <li><b>Leitura Universal:</b> Mapeamento recursivo de tags federais (vPis, vCofins, vRetCSLL).</li>
            <li><b>Análise Aritmética:</b> Cruzamento de Retenções vs Valor Líquido.</li>
            <li><b>Impostos Federais:</b> Captura de PIS, COFINS, CSLL e IRRF.</li>
            <li><b>Diagnóstico:</b> Explicação textual do erro encontrado.</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")

uploaded_files = st.file_uploader("Arraste os arquivos XML ou ZIP aqui", type=["xml", "zip"], accept_multiple_files=True)

if uploaded_files:
    if st.button("🚀 INICIAR AUDITORIA FISCAL"):
        data_rows = []
        with st.spinner("Processando..."):
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
                cols_fin = ['Vlr_Bruto', 'Vlr_Liquido', 'ISS_Valor', 'Ret_ISS', 'Ret_PIS', 'Ret_COFINS', 'Ret_CSLL', 'Ret_IRRF']
                for col in cols_fin:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)

                # --- LÓGICA DE DIAGNÓSTICO DETALHADO ---
                def realizar_diagnostico(r):
                    soma_retencoes = r['Ret_ISS'] + r['Ret_PIS'] + r['Ret_COFINS'] + r['Ret_CSLL'] + r['Ret_IRRF']
                    diferenca_apurada = round(r['Vlr_Bruto'] - r['Vlr_Liquido'], 2)
                    soma_retencoes = round(soma_retencoes, 2)
                    
                    if abs(diferenca_apurada - soma_retencoes) <= 0.02:
                        return "✅ Valores batem com as retenções identificadas."
                    elif diferenca_apurada == 0 and r['Vlr_Bruto'] > 0:
                        return "⚠️ Nota sem retenções (Bruto = Líquido)."
                    else:
                        gap = round(diferenca_apurada - soma_retencoes, 2)
                        return f"❌ Erro: Faltam R$ {gap} em retenções para fechar o Líquido."

                df['Diagnostico'] = df.apply(realizar_diagnostico, axis=1)

                cols = list(df.columns)
                if 'Ret_ISS' in cols and 'ISS_Valor' in cols:
                    cols.insert(cols.index('ISS_Valor') + 1, cols.pop(cols.index('Ret_ISS')))
                    df = df[cols]

                st.success(f"✅ {len(df)} notas processadas!")
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
                        else:
                            worksheet.set_column(i, i, 25)

                st.download_button(
                    label="📥 BAIXAR EXCEL AJUSTADO",
                    data=output.getvalue(),
                    file_name="portal_servtax_auditoria.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

# --- PRÓXIMO PASSO ---
# Os valores de PIS (20.14), COFINS (92.94) e CSLL (30.98) agora devem aparecer corretamente.
# Você gostaria que eu incluísse também a captura da Base de Cálculo (vBCPisCofins) em uma coluna separada?
