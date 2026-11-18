# Azure ML: training jobs, the model registry the release gate writes to, and evaluation runs.
resource "azurerm_machine_learning_workspace" "this" {
  name                          = "mlw-${local.name}"
  location                      = azurerm_resource_group.this.location
  resource_group_name           = azurerm_resource_group.this.name
  application_insights_id       = azurerm_application_insights.this.id
  key_vault_id                  = azurerm_key_vault.this.id
  storage_account_id            = azurerm_storage_account.aml.id
  container_registry_id         = azurerm_container_registry.this.id
  public_network_access_enabled = true
  identity {
    type = "SystemAssigned"
  }
  tags = local.tags
}

resource "azurerm_machine_learning_compute_cluster" "train" {
  name                          = "cpu-train"
  location                      = azurerm_resource_group.this.location
  machine_learning_workspace_id = azurerm_machine_learning_workspace.this.id
  vm_priority                   = "LowPriority"
  vm_size                       = "Standard_D8s_v5"
  identity {
    type = "SystemAssigned"
  }
  scale_settings {
    min_node_count                       = 0
    max_node_count                       = 4
    scale_down_nodes_after_idle_duration = "PT15M"
  }
}
