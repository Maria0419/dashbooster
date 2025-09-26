import requests
import os
import sys

# Load sensitive values from environment variables
tenantId = os.getenv('AZURE_TENANT_ID', 'your-tenant-id-here')
clientId = os.getenv('AZURE_CLIENT_ID', 'your-client-id-here')
clientSecret = os.getenv('AZURE_CLIENT_SECRET', 'your-client-secret-here')

def get_access_token(tenant_id: str, client_id: str, client_secret: str) -> str:
    """
    Obtém um access_token válido para usar na API do Power BI.
        str: Access token (Bearer token).
    """
    url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    
    data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": "https://analysis.windows.net/powerbi/api/.default"
    }
    
    response = requests.post(url, data=data)
    
    if response.status_code != 200:
        raise Exception(f"Erro ao obter token: {response.status_code}, {response.text}")
    
    return response.json()["access_token"]

import requests

def get_or_create_workspace(workspace_name: str, access_token: str) -> str:
    """
    Busca um workspace pelo nome. Se não existir, cria um novo workspace.
        str: ID do workspace existente ou recém-criado.
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    # Listar workspaces existentes
    url_list = "https://api.powerbi.com/v1.0/myorg/groups?workspaceV2=true"
    response = requests.get(url_list, headers=headers)
    if response.status_code != 200:
        raise Exception(f"Erro ao listar workspaces: {response.status_code}, {response.text}")
    
    workspaces = response.json().get("value", [])
    
    # Verifica se já existe
    for ws in workspaces:
        if ws.get("name") == workspace_name:
            print(f"Workspace '{workspace_name}' já existe. ID: {ws['id']}")
            return ws["id"]
    
    # Cria novo workspace
    url_create = "https://api.powerbi.com/v1.0/myorg/groups?workspaceV2=true"
    payload = {"name": workspace_name}
    response = requests.post(url_create, headers=headers, json=payload)
    
    if response.status_code not in (200, 201):
        raise Exception(f"Erro ao criar workspace: {response.status_code}, {response.text}")
    
    workspace_id = response.json().get("id")
    print(f"🆕 Workspace '{workspace_name}' criado com sucesso! ID: {workspace_id} ✅")
    return workspace_id


def add_user_to_workspace(workspace_id: str, access_token: str, user_email: str, role: str = "Admin"):
    """
    Adiciona um usuário a um workspace do Power BI, caso ainda não exista.
    Se já existir, apenas retorna a info.
    """
    url_users = f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/users"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    # 1. Verificar se o usuário já existe no workspace
    response = requests.get(url_users, headers=headers)
    if response.status_code != 200:
        raise Exception(f"Erro ao listar usuários: {response.status_code}, {response.text}")

    users = response.json().get("value", [])
    for user in users:
        if user.get("identifier", "").lower() == user_email.lower():
            print(f"👤 Usuário '{user_email}' já existe no workspace com acesso '{user['groupUserAccessRight']}' ✅")
            return user  # retorna os dados do usuário já existente

    # 2. Se não existe, adicionar
    payload = {
        "identifier": user_email,
        "groupUserAccessRight": role,
        "principalType": "User"
    }

    response = requests.post(url_users, headers=headers, json=payload)

    if response.status_code not in (200, 201):
        raise Exception(f"Erro ao adicionar usuário: {response.status_code}, {response.text}")

    print(f"👤 Usuário '{user_email}' adicionado com sucesso como '{role}' no workspace {workspace_id} ✅")
    return response.json() if response.text.strip() else None



def listar_powerbi(workspace_id, access_token):
    """
    Lista os relatórios (Power BI) de um workspace.
    :return: Lista de dicionários com 'id' e 'name' dos relatórios
    """
    url_reports = f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/reports"
    headers = {"Authorization": f"Bearer {access_token}"}

    response = requests.get(url_reports, headers=headers)

    if response.status_code != 200:
        print("Erro ao listar relatórios:", response.status_code, response.text)
        return []

    reports = response.json().get("value", [])
    lista_reports = [{"id": r["id"], "name": r["name"]} for r in reports]

    return lista_reports

def upload_pbix(workspace_id: str, access_token: str, dataset_name: str, pbix_file_path: str) -> str:
    """
    Faz upload de um arquivo PBIX para um workspace no Power BI.
    Returns:
        str: Import ID do upload realizado
    """
    print(f"📊 O relatório '{dataset_name}' não foi encontrado no workspace. ⬆️ Subindo... 🚀")

    #  Verifica arquivo PBIX
    if not os.path.exists(pbix_file_path):
        raise FileNotFoundError(f"Arquivo PBIX não encontrado em {pbix_file_path}")

    file_size = os.path.getsize(pbix_file_path)
    if file_size > 1024**3:  # 1 GB
        raise ValueError("PBIX maior que 1 GB, não é suportado via API REST")

    print(f"📁 Arquivo PBIX encontrado ({file_size / 1024**2:.2f} MB) ✅")

    # Monta URL do import
    url_import = (
        f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/imports"
        f"?datasetDisplayName={dataset_name}"
    )

    headers = {"Authorization": f"Bearer {access_token}"}

    # upload
    with open(pbix_file_path, "rb") as f:
        files = {"file": f}
        print("Iniciando upload do PBIX...")
        response = requests.post(url_import, headers=headers, files=files)

    if response.status_code not in [200, 202]:
        raise Exception(f"Erro no upload: {response.status_code}, {response.text}")

    import_data = response.json()
    import_id = import_data.get("id")
    print(f"📤 Upload bem-sucedido! Import ID: {import_id} ✅")

    return import_id

def get_dataset_id(workspaceId, access_token, dataset_name):
    headers = {"Authorization": f"Bearer {access_token}"}
    url_datasets = f"https://api.powerbi.com/v1.0/myorg/groups/{workspaceId}/datasets"
    response = requests.get(url_datasets, headers=headers)

    if response.status_code != 200:
        print("Erro ao listar datasets:", response.status_code, response.text)
        sys.exit(1)

    datasets = response.json().get("value", [])
    dataset_id = None
    for ds in datasets:
        if ds["name"] == dataset_name:
            dataset_id = ds["id"]
            break

    if dataset_id:
        print(f"📊 Dataset ID encontrado: {dataset_id} ✅")
    else:
        print("❌ Dataset não encontrado após o upload.")

    return dataset_id


def update_dataset_parameter(workspace_id: str, dataset_id: str, access_token: str, param_name: str, new_sql: str):
    """
    Atualiza o valor de um parâmetro em um dataset do Power BI.
    Returns:
        dict: Resposta da API do Power BI.
    """
    url = f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets/{dataset_id}/Default.UpdateParameters"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    payload = {
        "updateDetails": [
            {
                "name": param_name,
                "newValue": new_sql
            }
        ]
    }

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code != 200:
        raise Exception(f"Erro ao atualizar parâmetro: {response.status_code}, {response.text}")

    print(f"✅ Parâmetro '{param_name}' atualizado com sucesso! 🎉")
    return

def refresh_dataset(workspace_id: str, dataset_id: str, access_token: str):
    """
    Dispara o refresh de um dataset no Power BI.
    Returns: dict: Resposta da API do Power BI (contendo o ID do refresh iniciado).
    """
    url = f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets/{dataset_id}/refreshes"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    response = requests.post(url, headers=headers)

    if response.status_code not in (200, 202):
        raise Exception(f"Erro ao iniciar refresh: {response.status_code}, {response.text}")

    print(f"🔄 Refresh do dataset {dataset_id} iniciado com sucesso! ✅")
    return 

def get_report_url(workspace_id: str, access_token: str, report_name: str) -> str:
    """
    Retorna a URL web de um relatório no Power BI Service.
    """
    url_reports = f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/reports"
    headers = {"Authorization": f"Bearer {access_token}"}

    response = requests.get(url_reports, headers=headers)
    if response.status_code != 200:
        raise Exception(f"Erro ao listar relatórios: {response.status_code}, {response.text}")

    reports = response.json().get("value", [])
    for r in reports:
        if r["name"] == report_name:
            report_id = r["id"]
            report_url = f"https://app.powerbi.com/groups/{workspace_id}/reports/{report_id}"
            return report_url

    raise Exception(f"Relatório '{report_name}' não encontrado no workspace {workspace_id}.")



#Run

pbix_file_path = r"C:\Users\maria\Downloads\TesteDashbooster.pbix"  

workspace_name = "Dashbooster_API_Video"
user_email = "bu.tech@driva.com.br"

dataset_name = "Dashbooster_Video"

param_name = "param_sql_pneus_camaras"
sql = "SELECT * FROM SuaTabela LIMIT 5 -- Modificado via API"

access_token = get_access_token(tenantId, clientId, clientSecret)
print("🔑 Access Token obtido com sucesso.")

workspaceId = get_or_create_workspace(workspace_name, access_token)
print(f"🗂️  Workspace ID obtido: {workspaceId}")

add_user_to_workspace(workspaceId, access_token, user_email, role="Admin")

relatorios = listar_powerbi(workspaceId, access_token)

if dataset_name not in [r['name'] for r in relatorios]:
    upload_pbix(workspaceId, access_token, dataset_name, pbix_file_path)

datasetId = get_dataset_id(workspaceId, access_token, dataset_name)

update_dataset_parameter(workspaceId, datasetId, access_token, param_name, sql)
refresh_dataset(workspaceId, datasetId, access_token)

report_url = get_report_url(workspaceId, access_token, dataset_name)
print("🔗 URL do relatório:", report_url)


# embed token


def get_report_id(workspace_id: str, access_token: str, report_name: str) -> str:
    """
    Retorna o ID de um relatório no Power BI Service pelo nome.
    """
    url_reports = f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/reports"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    response = requests.get(url_reports, headers=headers)
    if response.status_code != 200:
        raise Exception(f"Erro ao listar relatórios: {response.status_code}, {response.text}")
    
    reports = response.json().get("value", [])
    for r in reports:
        if r["name"] == report_name:
            return r["id"]
    
    raise Exception(f"Relatório '{report_name}' não encontrado no workspace {workspace_id}.")


def get_embed_token(workspace_id, report_id, access_token):
    url = f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/reports/{report_id}/GenerateToken"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "accessLevel": "View"  # Can also be "Edit"
    }
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code != 200:
        raise Exception(f"Erro ao gerar embed token: {response.status_code}, {response.text}")
    return response.json()["token"]

report_name = dataset_name  # assuming report name == dataset name
report_id = get_report_id(workspaceId, access_token, report_name)

embed_token = get_embed_token(workspaceId, report_id, access_token)
print("🔑 Embed token:", embed_token)
