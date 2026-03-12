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
        # Busca recursiva profunda para encontrar tags em qualquer nível
        element = root.find(f".//{{*}}{tag}")
        if element is None:
            element = root.find(f".//{tag}")
        
        if element is not None and element.text:
            return element.text.strip()
            
    # Fallback para campos numéricos
    numeric_keywords = ['vlr', 'valor', 'iss', 'pis', 'cofins', 'ir', 'csll', 'liq', 'trib', 'v_', 'ded', 'dr', 'vserv', 'bc']
    if any(x in str(tags).lower() for x in numeric_keywords):
        return "0.00"
    return ""

def process_xml_file(content, filename):
    try:
        tree = ET.parse(io.BytesIO(content))
        root = tree.getroot()
        
        # Coleta de dados com mapeamento corrigido por tag específica
        row = {
            'Arquivo': filename,
            'Nota_Numero': get_xml_value(root, ['nNFSe', 'nDPS', 'NumeroNFe', 'nNF', 'numero', 'Numero']),
            'Data_Emissao': get_xml_value(root, ['dhProc', 'dhEmi', 'DataEmissao', 'dtEmi']),
            'Prestador_Razao': get_xml_value(root, ['emit/xNome', 'RazaoSocialPrestador', 'xNomePrestador', 'xNome']),
            
            # VALORES BASE
            'Vlr_Bruto': get_xml_value(root, ['vServ', 'vServPrest', 'ValorServicos', 'vNF', 'ValorTotal']),
            'Vlr_Deducao': get_xml_value(root, ['vDedRed', 'vDR', 'vDeducao', 'ValorDeducao']),
            'Vlr_Liquido': get_xml_value(root, ['vLiq', 'vLiquido', 'ValorLiquidoNFe', 'vLiqNFSe', 'vServPrest/vLiq']),
            
            # IMPOSTOS MUNICIPAIS
            'ISS_Valor': get_xml_value(root, ['vISSQN', 'vISS', 'ValorISS', 'vISS_Ret', 'vISSRetido']),
            
            # IMPOSTOS FEDERAIS (Mapeamento Cirúrgico)
            'Ret_PIS': get_xml_value(root, ['vPis', 'vPIS', 'vRetPIS', 'ValorPIS', 'vPIS_Ret']),
            'Ret_COFINS': get_xml_value(root, ['vCofins', 'vCOFINS', 'vRetCOFINS', 'ValorCOFINS', 'vCOFINS_Ret']),
            'Ret_CSLL': get_xml_value(root, ['vRetCSLL', 'vCSLL', 'ValorCSLL', 'vCSLL_Ret']),
            'Ret_IRRF': get_xml_value(root, ['vRetIRRF', 'vIRRF', 'vIR', 'ValorIR', 'vIR_Ret']),
            
            # BASE DE CÁLCULO PIS/COFINS
            'BC_PIS_COFINS': get_xml_value(root, ['vBCPisCofins', 'vBCPISCOFINS', 'vBCPIS', 'vBCCOFINS']),
            
            'Descricao': get_xml_value(root, ['xDescServ', 'Discriminacao', 'xServ', 'infCpl'])
        }

        # Lógica de Captura de ISS Retido (Checa flags e tags de valor retido)
        v_bruto = float(row['Vlr_Bruto'])
        v_liq = float(row['Vlr_Liquido'])
        v_iss_calc = float(row['ISS_Valor'])
        
        iss_retido_tag = get_xml_value(root, ['ISSRetido', 'tpRetISSQN', 'tpRetISS'])
        
        # Se a flag for de retenção ou se o líquido for menor que o bruto descontando o ISS
        if iss_retido_tag in ['true', '2', '1'] or (v_bruto - v_liq >= v_iss_calc and v_iss_calc > 0):
            row['Ret_ISS_Apurado'] = v_iss_calc
        else:
            row['Ret_ISS_Apurado'] = 0.00
             
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
                
                # Conversão e Limpeza
                cols_fin = ['Vlr_Bruto', 'Vlr_Deducao', 'Vlr_Liquido', 'ISS_Valor', 'Ret_ISS_Apurado', 'Ret_PIS', 'Ret_COFINS', 'Ret_CSLL', 'Ret_IRRF']
                for col in cols_fin:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)

                # --- DIAGNÓSTICO DE PROVA REAL (MÚLTIPLOS TESTES) ---
                def realizar_diagnostico(r):
                    v_bruto = round(r['Vlr_Bruto'], 2)
                    v_liq = round(r['Vlr_Liquido'], 2)
                    v_ded = round(r['Vlr_Deducao'], 2)
                    s_fed = round(r['Ret_PIS'] + r['Ret_COFINS'] + r['Ret_CSLL'] + r['Ret_IRRF'], 2)
                    s_iss = round(r['Ret_ISS_Apurado'], 2)
                    
                    diff = round(v_bruto - v_liq, 2)

                    # Teste 1: Serviço Padrão (Bruto - Retenções Federais - ISS Retido = Líquido)
                    if abs(diff - (s_fed + s_iss)) <= 0.05:
                        return "✅ Ok: Retenções batem."
                    
                    # Teste 2: Construção Civil (Bruto - Dedução - Retenções = Líquido)
                    if abs(diff - (v_ded + s_fed + s_iss)) <= 0.05:
                        return "✅ Ok: Dedução + Retenções batem."
                    
                    # Teste 3: Apenas Dedução
                    if abs(diff - v_ded) <= 0.05:
                        return "✅ Ok: Diferença é apenas dedução."

                    gap = round(diff - (v_ded + s_fed + s_iss), 2)
                    return f"❌ Erro: Discrepância de R$ {gap}"

                df['Diagnostico'] = df.apply(realizar_diagnostico, axis=1)

                # Organização de Colunas
                ordem = ['Arquivo', 'Nota_Numero', 'Vlr_Bruto', 'Vlr_Deducao', 'Vlr_Liquido', 'ISS_Valor', 'Ret_ISS_Apurado', 'Ret_PIS', 'Ret_COFINS', 'Ret_CSLL', 'Ret_IRRF', 'Diagnostico']
                df = df[ordem]

                # Linha de Subtotal
                total_row = {col: "" for col in df.columns}
                total_row['Arquivo'] = "TOTAL GERAL"
                for col in cols_fin:
                    if col in df.columns:
                        total_row[col] = df[col].sum()
                
                df_final = pd.concat([df, pd.DataFrame([total_row])], ignore_index=True)

                st.success(f"✅ {len(df)} notas processadas!")
                st.dataframe(df_final)

                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df_final.to_excel(writer, index=False, sheet_name='PortalServTax')
                    workbook = writer.book
                    worksheet = writer.sheets['PortalServTax']
                    
                    header_fmt = workbook.add_format({'bold': True, 'bg_color': '#FF69B4', 'font_color': 'white', 'border': 1})
                    num_fmt = workbook.add_format({'num_format': '#,##0.00', 'border': 1})
                    total_fmt = workbook.add_format({'bold': True, 'bg_color': '#FFE4F2', 'num_format': '#,##0.00', 'border': 1})
                    error_fmt = workbook.add_format({'font_color': 'red', 'border': 1})
                    
                    worksheet.autofilter(0, 0, len(df_final)-1, len(df_final.columns)-1)
                    
                    for i, col in enumerate(df_final.columns):
                        worksheet.write(0, i, col, header_fmt)
                        if col in cols_fin:
                            worksheet.set_column(i, i, 18, num_fmt)
                        else:
                            worksheet.set_column(i, i, 25)
                    
                    diag_idx = df_final.columns.get_loc('Diagnostico')
                    worksheet.conditional_format(1, diag_idx, len(df_final)-1, diag_idx, {
                        'type': 'text', 'criteria': 'containing', 'value': 'Erro', 'format': error_fmt
                    })
                    
                    for i, col in enumerate(df_final.columns):
                        val = df_final.iloc[-1][col]
                        worksheet.write(len(df_final), i, val, total_fmt)

                st.download_button(label="📥 BAIXAR EXCEL AUDITADO", data=output.getvalue(), file_name="auditoria_fiscal.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# --- PRÓXIMO PASSO ---
# Esta versão garante que vRetPIS, vRetCOFINS, vRetCSLL e vRetIRRF caiam nas colunas certas.
# Rodamos o teste com a nota da T-Systems e a de Obra simultaneamente para validar?
