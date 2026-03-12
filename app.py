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
        </style>
    """, unsafe_allow_html=True)

aplicar_estilo_sentinela_zonas()

# --- LÓGICA DE PROCESSAMENTO ---
def get_xml_value(root, tags):
    for tag in tags:
        element = root.find(f".//{{*}}{tag}")
        if element is None:
            element = root.find(f".//{tag}")
        if element is not None and element.text:
            return element.text.strip()
            
    numeric_keywords = ['vlr', 'valor', 'iss', 'pis', 'cofins', 'ir', 'csll', 'liq', 'trib', 'v_', 'ded', 'dr', 'vserv', 'bc']
    if any(x in str(tags).lower() for x in numeric_keywords):
        return "0.00"
    return ""

def process_xml_file(content, filename):
    try:
        tree = ET.parse(io.BytesIO(content))
        root = tree.getroot()
        
        # Captura de Flags de Retenção
        iss_retido_flag = get_xml_value(root, ['ISSRetido']).lower()
        tp_ret_iss = get_xml_value(root, ['tpRetISSQN', 'tpRetISS'])
        tp_ret_piscofins = get_xml_value(root, ['tpRetPisCofins'])
        
        row = {
            'Arquivo': filename,
            'Nota_Numero': get_xml_value(root, ['nNFSe', 'NumeroNFe', 'nNF', 'numero', 'Numero']),
            'Data_Emissao': get_xml_value(root, ['dhProc', 'dhEmi', 'DataEmissaoNFe', 'DataEmissao', 'dtEmi']),
            'Prestador_CNPJ': get_xml_value(root, ['emit/CNPJ', 'CPFCNPJPrestador/CNPJ', 'CNPJPrestador', 'emit_CNPJ', 'CPFCNPJPrestador/CPF', 'CNPJ']),
            'Prestador_Razao': get_xml_value(root, ['emit/xNome', 'RazaoSocialPrestador', 'xNomePrestador', 'emit_xNome', 'RazaoSocial', 'xNome']),
            'Tomador_CNPJ': get_xml_value(root, ['toma/CNPJ', 'CPFCNPJTomador/CNPJ', 'CPFCNPJTomador/CPF', 'dest/CNPJ', 'CNPJTomador', 'toma/CPF', 'tom/CNPJ', 'CNPJ']),
            'Tomador_Razao': get_xml_value(root, ['toma/xNome', 'RazaoSocialTomador', 'dest/xNome', 'xNomeTomador', 'RazaoSocialTomador', 'tom/xNome', 'xNome']),
            'Vlr_Bruto': get_xml_value(root, ['vServ', 'vServPrest/vServ', 'ValorServicos', 'vNF', 'ValorTotal']),
            'Vlr_Deducao': get_xml_value(root, ['vDedRed', 'vDR', 'vDeducao', 'ValorDeducao']),
            'BC_PIS_COFINS': get_xml_value(root, ['vBCPisCofins', 'vBCPISCOFINS', 'vBCPIS', 'vBCCOFINS']),
            'Vlr_Liquido': get_xml_value(root, ['vLiq', 'ValorLiquidoNFe', 'vLiqNFSe', 'vLiquido', 'vServPrest/vLiq']),
            'ISS_Valor': get_xml_value(root, ['vISS', 'ValorISS', 'vISSQN', 'iss/vISS']),
            'Ret_PIS': get_xml_value(root, ['vPis', 'vPIS', 'ValorPIS', 'vPIS_Ret', 'PISRetido', 'vRetPIS']),
            'Ret_COFINS': get_xml_value(root, ['vCofins', 'vCOFINS', 'ValorCOFINS', 'vCOFINS_Ret', 'COFINSRetido', 'vRetCOFINS']),
            'Ret_CSLL': get_xml_value(root, ['vRetCSLL', 'vCSLL', 'ValorCSLL', 'vCSLL_Ret', 'CSLLRetido', 'vRetCSLL']),
            'Ret_IRRF': get_xml_value(root, ['vRetIRRF', 'vIRRF', 'vIR', 'ValorIR', 'vIR_Ret', 'IRRetido', 'vRetIR']),
            'Descricao': get_xml_value(root, ['CodigoServico', 'itemServico', 'cServ', 'xDescServ', 'Discriminacao', 'xServ', 'infCpl', 'xProd'])
        }

        # Lógica rigorosa de Retenção de ISS
        if tp_ret_iss == '2' or iss_retido_flag == 'true':
             row['Ret_ISS_Apurado'] = float(get_xml_value(root, ['vTotTribMun', 'vISSRetido', 'ValorISS_Retido', 'vRetISS', 'vISSRet', 'iss/vRet']))
        else:
             row['Ret_ISS_Apurado'] = 0.00

        # Lógica rigorosa de Retenção de PIS/COFINS (tpRet 2 = Retido)
        if tp_ret_piscofins == '2':
            row['Ret_PIS_Apurado'] = float(row['Ret_PIS'])
            row['Ret_COFINS_Apurado'] = float(row['Ret_COFINS'])
        else:
            row['Ret_PIS_Apurado'] = 0.00
            row['Ret_COFINS_Apurado'] = 0.00

        # IRRF e CSLL (Geralmente quando vêm no bloco tribFed são retidos, mas mantemos o mapeamento)
        row['Ret_CSLL_Apurado'] = float(row['Ret_CSLL'])
        row['Ret_IRRF_Apurado'] = float(row['Ret_IRRF'])
             
        return row
    except:
        return None

# --- ÁREA VISUAL ---
st.title("PORTAL TAX NFS-e - AUDITORIA FISCAL")

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
                
                # Conversão numérica
                cols_to_convert = ['Vlr_Bruto', 'Vlr_Deducao', 'Vlr_Liquido', 'Ret_ISS_Apurado', 'Ret_PIS_Apurado', 'Ret_COFINS_Apurado', 'Ret_CSLL_Apurado', 'Ret_IRRF_Apurado']
                for col in cols_to_convert:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)

                def realizar_diagnostico(r):
                    v_bruto = round(r['Vlr_Bruto'], 2)
                    v_ded = round(r['Vlr_Deducao'], 2)
                    v_liq = round(r['Vlr_Liquido'], 2)
                    
                    # Soma apenas o que foi identificado como RETIDO pelas flags do XML
                    soma_retencoes = round(r['Ret_ISS_Apurado'] + r['Ret_PIS_Apurado'] + r['Ret_COFINS_Apurado'] + r['Ret_CSLL_Apurado'] + r['Ret_IRRF_Apurado'], 2)
                    
                    # Teste A: Bruto - Retenções = Líquido (Dedução informativa)
                    if abs(round(v_bruto - soma_retencoes, 2) - v_liq) <= 0.05:
                        return "✅ Ok: Bruto - Retenções = Líquido"
                    
                    # Teste B: Bruto - Dedução - Retenções = Líquido (Dedução financeira)
                    if abs(round(v_bruto - v_ded - soma_retencoes, 2) - v_liq) <= 0.05:
                        return "✅ Ok: Bruto - Dedução - Retenções = Líquido"

                    gap = round(v_bruto - v_ded - soma_retencoes - v_liq, 2)
                    return f"❌ Erro: Discrepância de R$ {gap}"

                df['Diagnostico'] = df.apply(realizar_diagnostico, axis=1)

                # Organização de Colunas
                final_cols = ['Arquivo', 'Nota_Numero', 'Vlr_Bruto', 'Vlr_Deducao', 'Vlr_Liquido', 'Ret_ISS_Apurado', 'Ret_PIS_Apurado', 'Ret_COFINS_Apurado', 'Ret_CSLL_Apurado', 'Ret_IRRF_Apurado', 'Diagnostico', 'Descricao']
                df_final = df[final_cols]

                # Linha de Subtotal
                total_row = {col: "" for col in df_final.columns}
                total_row['Arquivo'] = "TOTAL GERAL"
                for col in final_cols:
                    if 'Vlr' in col or 'Ret' in col:
                        total_row[col] = df_final[col].sum()
                
                df_with_total = pd.concat([df_final, pd.DataFrame([total_row])], ignore_index=True)

                st.success(f"✅ {len(df)} notas processadas!")
                st.dataframe(df_with_total)

                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df_with_total.to_excel(writer, index=False, sheet_name='PortalServTax')
                    workbook = writer.book
                    worksheet = writer.sheets['PortalServTax']
                    
                    header_fmt = workbook.add_format({'bold': True, 'bg_color': '#FF69B4', 'font_color': 'white', 'border': 1})
                    num_fmt = workbook.add_format({'num_format': '#,##0.00', 'border': 1})
                    total_fmt = workbook.add_format({'bold': True, 'bg_color': '#FFE4F2', 'num_format': '#,##0.00', 'border': 1})
                    error_txt_fmt = workbook.add_format({'font_color': 'red', 'border': 1})
                    
                    num_rows = len(df_with_total)
                    num_cols = len(df_with_total.columns)
                    worksheet.autofilter(0, 0, num_rows - 1, num_cols - 1)
                    
                    for i, col in enumerate(df_with_total.columns):
                        worksheet.write(0, i, col, header_fmt)
                        if 'Vlr' in col or 'Ret' in col:
                            worksheet.set_column(i, i, 18, num_fmt)
                        else:
                            worksheet.set_column(i, i, 25)
                    
                    diag_col_idx = df_with_total.columns.get_loc('Diagnostico')
                    worksheet.conditional_format(1, diag_col_idx, num_rows - 1, diag_col_idx, {
                        'type': 'text', 'criteria': 'containing', 'value': 'Erro', 'format': error_txt_fmt
                    })
                    
                    for i, col in enumerate(df_with_total.columns):
                        val = df_with_total.iloc[-1][col]
                        worksheet.write(num_rows, i, val, total_fmt)

                st.download_button(label="📥 BAIXAR EXCEL AUDITADO", data=output.getvalue(), file_name="portal_servtax_auditoria.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# --- PRÓXIMO PASSO ---
# Esta versão agora entende que tpRetPisCofins = 2 significa que o PIS/COFINS devem ser subtraídos do líquido.
# Deseja testar essa nota de 308.48 agora?
