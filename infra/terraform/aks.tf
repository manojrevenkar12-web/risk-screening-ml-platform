resource "azurerm_kubernetes_cluster" "this" {
  name                      = "aks-${local.name}"
  location                  = azurerm_resource_group.this.location
  resource_group_name       = azurerm_resource_group.this.name
  dns_prefix                = local.name
  sku_tier                  = var.environment == "prod" ? "Standard" : "Free"
  oidc_issuer_enabled       = true
  workload_identity_enabled = true
  local_account_disabled    = true

  default_node_pool {
    name                         = "system"
    vm_size                      = "Standard_D2s_v5"
    auto_scaling_enabled         = true
    min_count                    = 1
    max_count                    = 3
    only_critical_addons_enabled = true
    upgrade_settings {
      max_surge = "33%"
    }
  }

  identity {
    type = "SystemAssigned"
  }

  azure_active_directory_role_based_access_control {
    azure_rbac_enabled = true
    tenant_id          = data.azurerm_client_config.current.tenant_id
  }

  workload_autoscaler_profile {
    keda_enabled = true
  }

  oms_agent {
    log_analytics_workspace_id      = azurerm_log_analytics_workspace.this.id
    msi_auth_for_monitoring_enabled = true
  }

  network_profile {
    network_plugin      = "azure"
    network_policy      = "cilium"
    network_data_plane  = "cilium"
    network_plugin_mode = "overlay"
  }

  tags = local.tags
}

resource "azurerm_kubernetes_cluster_node_pool" "scorer" {
  name                  = "scorer"
  kubernetes_cluster_id = azurerm_kubernetes_cluster.this.id
  vm_size               = var.scorer_vm_size
  auto_scaling_enabled  = true
  min_count             = var.scorer_nodes.min
  max_count             = var.scorer_nodes.max
  node_labels           = { "workload" = "scorer" }
  node_taints           = ["workload=scorer:NoSchedule"]
  tags                  = local.tags
}

resource "azurerm_role_assignment" "aks_acr_pull" {
  scope                            = azurerm_container_registry.this.id
  role_definition_name             = "AcrPull"
  principal_id                     = azurerm_kubernetes_cluster.this.kubelet_identity[0].object_id
  skip_service_principal_aad_check = true
}
