# Workloads authenticate with Entra ID through AKS workload identity: no keys in pods or in Key Vault.
locals {
  workloads = {
    scorer  = "relevance-scorer"
    tagger  = "llm-tagger"
    gateway = "llm-gateway"
  }
}

resource "azurerm_user_assigned_identity" "workload" {
  for_each            = local.workloads
  name                = "id-${local.name}-${each.key}"
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  tags                = local.tags
}

resource "azurerm_federated_identity_credential" "workload" {
  for_each            = local.workloads
  name                = "fic-${each.key}"
  resource_group_name = azurerm_resource_group.this.name
  parent_id           = azurerm_user_assigned_identity.workload[each.key].id
  audience            = ["api://AzureADTokenExchange"]
  issuer              = azurerm_kubernetes_cluster.this.oidc_issuer_url
  subject             = "system:serviceaccount:screening:${each.value}"
}

resource "azurerm_role_assignment" "scorer_eventhubs" {
  for_each             = toset(["Azure Event Hubs Data Receiver", "Azure Event Hubs Data Sender"])
  scope                = azurerm_eventhub_namespace.this.id
  role_definition_name = each.key
  principal_id         = azurerm_user_assigned_identity.workload["scorer"].principal_id
}

resource "azurerm_role_assignment" "scorer_models" {
  scope                = azurerm_storage_account.lake.id
  role_definition_name = "Storage Blob Data Reader"
  principal_id         = azurerm_user_assigned_identity.workload["scorer"].principal_id
}

resource "azurerm_role_assignment" "tagger_openai" {
  for_each             = local.openai_regions
  scope                = azurerm_cognitive_account.openai[each.key].id
  role_definition_name = "Cognitive Services OpenAI User"
  principal_id         = azurerm_user_assigned_identity.workload["tagger"].principal_id
}

resource "azurerm_role_assignment" "tagger_eventhubs" {
  scope                = azurerm_eventhub_namespace.this.id
  role_definition_name = "Azure Event Hubs Data Receiver"
  principal_id         = azurerm_user_assigned_identity.workload["tagger"].principal_id
}

# People never call Azure OpenAI directly: only the gateway's identity can, and it enforces per-group deployments,
# quotas and budgets (Azure RBAC on an account cannot narrow access to one deployment).
resource "azurerm_role_assignment" "gateway_openai" {
  scope                = azurerm_cognitive_account.openai["primary"].id
  role_definition_name = "Cognitive Services OpenAI User"
  principal_id         = azurerm_user_assigned_identity.workload["gateway"].principal_id
}

resource "azurerm_role_assignment" "ml_engineers_aml" {
  for_each             = { for k, g in var.team_groups : k => g if contains(g.deployments, "sandbox") }
  scope                = azurerm_machine_learning_workspace.this.id
  role_definition_name = "AzureML Data Scientist"
  principal_id         = each.value.object_id
}
