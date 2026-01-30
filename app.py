import xml.etree.ElementTree as ET
import os

def extrair_dados_nfs_padrão_nacional(caminho_arquivo):
    """
    Realiza o parse de arquivos XML de NFSe (Padrão Nacional) mantendo a integridade 
    da lógica de processamento e hierarquia fiscal.
    """
    try:
        tree = ET.parse(caminho_arquivo)
        root = tree.getroot()

        # Definição de namespaces comumente encontrados em NFSe Nacional e SP
        ns = {
            'nfs': 'http://www.sped.fazenda.gov.br/nfse',
            'ds': 'http://www.w3.org/2000/09/xmldsig#',
            'sp': 'http://www.prefeitura.sp.gov.br/nfe'
        }

        # Localizar a tag principal de informação (infNFSe ou NFe)
        inf_nfse = root.find('.//nfs:infNFSe', ns)
        if inf_nfse is None:
            inf_nfse = root.find('.//sp:NFe', ns)
            if inf_nfse is None:
                inf_nfse = root # Tenta a raiz caso não haja namespace definido

        # --- Coleta de Dados de Identificação da Nota ---
        dados = {
            "numero_nfse": None,
            "data_emissao": None,
            "valor_servicos": None,
            "prestador": {
                "cnpj_cpf": None,
                "razao_social": None
            },
            "tomador": {
                "cnpj_cpf": None,
                "razao_social": None
            }
        }

        # Número e Data
        n_nfse = inf_nfse.find('.//nfs:nNFSe', ns)
        if n_nfse is None: n_nfse = inf_nfse.find('.//nNFSe')
        dados["numero_nfse"] = n_nfse.text if n_nfse is not None else None

        dh_proc = inf_nfse.find('.//nfs:dhProc', ns)
        if dh_proc is None: dh_proc = inf_nfse.find('.//dhProc')
        dados["data_emissao"] = dh_proc.text if dh_proc is not None else None

        # --- PRESTADOR (Emitente) ---
        emit = inf_nfse.find('.//nfs:emit', ns) or inf_nfse.find('.//emit')
        if emit is not None:
            cnpj = emit.find('.//nfs:CNPJ', ns) or emit.find('.//CNPJ')
            nome = emit.find('.//nfs:xNome', ns) or emit.find('.//xNome')
            dados["prestador"]["cnpj_cpf"] = cnpj.text if cnpj is not None else None
            dados["prestador"]["razao_social"] = nome.text if nome is not None else None
        else:
            # Caso para o layout de SP
            prestador_sp = inf_nfse.find('.//CPFCNPJPrestador')
            if prestador_sp is not None:
                cnpj_sp = prestador_sp.find('CNPJ') or prestador_sp.find('CPF')
                dados["prestador"]["cnpj_cpf"] = cnpj_sp.text if cnpj_sp is not None else None
            razao_sp = inf_nfse.find('.//RazaoSocialPrestador')
            dados["prestador"]["razao_social"] = razao_sp.text if razao_sp is not None else None

        # --- TOMADOR (Destinatário) ---
        tomador = inf_nfse.find('.//nfs:tom', ns) or inf_nfse.find('.//tom')
        if tomador is not None:
            # Busca CNPJ ou CPF no padrão nacional
            ident_tomador = tomador.find('.//nfs:CNPJ', ns) or tomador.find('.//nfs:CPF', ns) or \
                           tomador.find('.//CNPJ') or tomador.find('.//CPF')
            nome_tomador = tomador.find('.//nfs:xNome', ns) or tomador.find('.//xNome')
            
            dados["tomador"]["cnpj_cpf"] = ident_tomador.text if ident_tomador is not None else None
            dados["tomador"]["razao_social"] = nome_tomador.text if nome_tomador is not None else None
        else:
            # Caso para o layout de SP
            tomador_sp = inf_nfse.find('.//CPFCNPJTomador')
            if tomador_sp is not None:
                cnpj_sp = tomador_sp.find('CNPJ') or tomador_sp.find('CPF')
                dados["tomador"]["cnpj_cpf"] = cnpj_sp.text if cnpj_sp is not None else None
            razao_sp = inf_nfse.find('.//RazaoSocialTomador')
            dados["tomador"]["razao_social"] = razao_sp.text if razao_sp is not None else None

        # --- VALORES ---
        valores = inf_nfse.find('.//nfs:valores', ns) or inf_nfse.find('.//valores')
        if valores is not None:
            v_serv = valores.find('.//nfs:vServ', ns) or valores.find('.//vServ')
            dados["valor_servicos"] = v_serv.text if v_serv is not None else None
        else:
            # Padrão SP
            v_serv_sp = inf_nfse.find('.//ValorServicos')
            dados["valor_servicos"] = v_serv_sp.text if v_serv_sp is not None else None

        return dados

    except Exception as e:
        return {"erro": f"Falha no processamento do arquivo: {str(e)}"}

# Exemplo de execução para os arquivos carregados
if __name__ == "__main__":
    # Lista simulada de arquivos para o exemplo
    arquivos = [f for f in os.listdir('.') if f.endswith('.xml')]
    
    for arquivo in arquivos:
        resultado = extrair_dados_nfs_padrão_nacional(arquivo)
        print(f"Arquivo: {arquivo}")
        print(f"Resultado: {resultado}")
        print("-" * 50)
