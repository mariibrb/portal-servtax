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
        # BUSCA RECURSIVA PROFUNDA MANTIDA
        element = root.find(f".//{{*}}{tag}")
        if element is None:
            element = root.find(f".//{tag}")
        if element is not None and element.text:
            return element.text.strip()
    # Mantenho a regra de retorno de 0.00 para campos financeiros
    return "0.00" if any(x in str(tags).lower() for x in ['vlr', 'valor', 'iss', 'pis', 'cofins', 'ir', 'csll', 'liquido', 'trib', 'bc', 'ded', 'dr', 'serv', 'liq']) else ""

def process_xml_file(content, filename):
    try:
        tree = ET.parse(io.BytesIO(content))
        root = tree.getroot()
        iss_retido_flag = get_xml_value(root, ['ISSRetido']).lower()
        tp_ret_flag = get_xml_value(root, ['tpRetISSQN', 'tpRetISS'])
        
        # RESTAURAÇÃO INTEGRAL DE TODAS AS COLUNAS COM ACRÉSCIMO DE TAGS
        row = {
            'Arquivo': filename,
            'Nota_Numero': get_xml_value(root, ['nNFSe', 'NumeroNFe', 'nNF', 'numero', 'Numero', 'nDPS']),
            'Data_Emissao': get_xml_value(root, ['dhProc', 'dhEmi', 'DataEmissaoNFe', 'DataEmissao', 'dtEmi']),
            'Prestador_CNPJ': get_xml_value(root, ['emit/CNPJ', 'CPFCNPJPrestador/CNPJ', 'CNPJPrestador', 'emit_CNPJ', 'CPFCNPJPrestador/CPF', 'CNPJ']),
            'Prestador_Razao': get_xml_value(root, ['emit/xNome', 'RazaoSocialPrestador', 'xNomePrestador', 'emit_xNome', 'RazaoSocial', 'xNome']),
            'Tomador_CNPJ': get_xml_value(root, ['toma/CNPJ', 'CPFCNPJTomador/CNPJ', 'CPFCNPJTomador/CPF', 'dest/CNPJ', 'CNPJTomador', 'toma/CPF', 'tom/CNPJ', 'CNPJ']),
            'Tomador_Razao': get_xml_value(root, ['toma/xNome', 'RazaoSocialTomador', 'dest/xNome', 'xNomeTomador', 'RazaoSocialTomador', 'tom/xNome', 'xNome']),
            
            # VALORES BASE (RESTAURADOS)
            'Vlr_Bruto': get_xml_value(root, ['vServ', 'ValorServicos', 'vNF', 'vServPrest/vServ', 'ValorTotal', 'vServPrest']),
            'Vlr_Deducao': get_xml_value(root, ['vDedRed', 'vDR', 'vDeducao', 'ValorDeducao']),
            'BC_PIS_COFINS': get_xml_value(root, ['vBCPisCofins', 'vBCPISCOFINS', 'vBCPIS', 'vBCCOFINS', 'vBC']),
            'Vlr_Liquido': get_xml_value(root, ['vLiq', 'ValorLiquidoNFe', 'vLiqNFSe', 'vLiquido', 'vServPrest/vLiq']),
            
            # IMPOSTOS (RESTAURADOS)
            'ISS_Valor': get_xml_value(root, ['vISS', 'ValorISS', 'vISSQN', 'iss/vISS']),
            'Ret_PIS': get_xml_value(root, ['vPIS', 'ValorPIS', 'vPIS_Ret', 'PISRetido', 'vRetPIS', 'vPis']),
            'Ret_COFINS': get_xml_value(root, ['vCOFINS', 'ValorCOFINS', 'vCOFINS_Ret', 'COFINSRetido', 'vRetCOFINS', 'vCofins']),
            'Ret_CSLL': get_xml_value(root, ['vCSLL', 'ValorCSLL', 'vCSLL_Ret', 'CSLLRetido', 'vRetCSLL']),
            'Ret_IRRF': get_xml_value(root, ['vIR', 'ValorIR', 'vIR_Ret', 'IRRetido', 'vRetIR', 'vIRRF', 'vRetIRRF']),
            'Descricao': get_xml_value(root, ['CodigoServico', 'itemServico', 'cServ', 'xDescServ', 'Discriminacao', 'xServ', 'infCpl', 'xProd'])
        }

        # Lógica de ISS Retido original de ontem
        v_total_ret_tag = float(get_xml_value(root, ['vTotalRet']))
        if tp_ret_flag == '2' or iss_retido_flag == 'true' or v_total_ret_tag > 0:
             row['Ret_ISS'] = row['ISS_Valor']
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
            <li><b>Conferência:</b> Analise o <b>Diagnóstico</b> de divergências.</li>
            <li><b>Saída:</b> Baixe o Excel final para auditoria.</li>
        </ol>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
    <div class="instrucoes-card">
        <h3>📊 O que será obtido?</h3>
        <ul>
            <li><b>Leitura Universal:</b> Dados de centenas de prefeituras consolidados.</li>
            <li><b>Gestão de ISS:</b> Separação entre ISS Próprio e Retido.</li>
            <li><b>Impostos Federais:</b> Captura de PIS, COFINS, CSLL e IRRF.</li>
            <li><b>Diagnóstico:</b> Identificação de notas com retenções pendentes.</li>
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
                # Todas as colunas financeiras originais de volta
                cols_fin = ['Vlr_Bruto', 'Vlr_Deducao', 'BC_PIS_COFINS', 'Vlr_Liquido', 'ISS_Valor', 'Ret_ISS', 'Ret_PIS', 'Ret_COFINS', 'Ret_CSLL', 'Ret_IRRF']
                for col in cols_fin:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)

                # DIAGNÓSTICO MULTICENÁRIO PARA NÃO DAR ERRO NAS NOTAS CERTAS
                def realizar_diagnostico(r):
                    soma_ret = round(r['Ret_ISS'] + r['Ret_PIS'] + r['Ret_COFINS'] + r['Ret_CSLL'] + r['Ret_IRRF'], 2)
                    diff = round(r['Vlr_Bruto'] - r['Vlr_Liquido'], 2)
                    v_ded = round(r['Vlr_Deducao'], 2)

                    if abs(diff - soma_ret) <= 0.05: return "✅"
                    if abs(diff - (soma_ret + v_ded)) <= 0.05: return "✅"
                    if abs(diff - v_ded) <= 0.05: return "✅"
                    
                    gap = round(diff - (soma_ret + v_ded), 2)
                    return f"⚠️ Divergência R$ {gap}"

                df['Diagnostico'] = df.apply(realizar_diagnostico, axis=1)

                # ORDENAÇÃO COMPLETA DAS COLUNAS
                cols = [
                    'Arquivo', 'Nota_Numero', 'Data_Emissao', 'Prestador_Razao', 'Prestador_CNPJ',
                    'Tomador_Razao', 'Tomador_CNPJ', 'Vlr_Bruto', 'Vlr_Deducao', 'BC_PIS_COFINS', 
                    'Vlr_Liquido', 'ISS_Valor', 'Ret_ISS', 'Ret_PIS', 'Ret_COFINS', 'Ret_CSLL', 
                    'Ret_IRRF', 'Diagnostico', 'Descricao'
                ]
                df = df[[c for c in cols if c in df.columns]]

                # SUBTOTAIS
                total_row = {col: "" for col in df.columns}
                total_row['Arquivo'] = "TOTAL GERAL"
                for col in cols_fin:
                    total_row[col] = df[col].sum()
                df_with_total = pd.concat([df, pd.DataFrame([total_row])], ignore_index=True)

                st.success(f"✅ {len(df)} notas processadas!")
                st.dataframe(df_with_total)

                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df_with_total.to_excel(writer, index=False, sheet_name='PortalServTax')
                    workbook = writer.book
                    worksheet = writer.sheets['PortalServTax']
                    header_fmt = workbook.add_format({'bold': True, 'bg_color': '#FF69B4', 'font_color': 'white', 'border': 1})
                    num_fmt = workbook.add_format({'num_format': '#,##0.00'})
                    total_fmt = workbook.add_format({'bold': True, 'bg_color': '#FFE4F2', 'num_format': '#,##0.00', 'border': 1})
                    
                    worksheet.autofilter(0, 0, len(df_with_total)-1, len(df_with_total.columns)-1)
                    
                    for i, col in enumerate(df_with_total.columns):
                        worksheet.write(0, i, col, header_fmt)
                        if col in cols_fin:
                            worksheet.set_column(i, i, 18, num_fmt)
                        else:
                            worksheet.set_column(i, i, 22)
                    
                    # Linha de total no Excel
                    for i, col in enumerate(df_with_total.columns):
                        val = df_with_total.iloc[-1][col]
                        worksheet.write(len(df_with_total), i, val, total_fmt)

                st.download_button(
                    label="📥 BAIXAR EXCEL AJUSTADO",
                    data=output.getvalue(),
                    file_name="portal_servtax_auditoria.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
