# Platform metadata: release decisions, gateway audit and spend, drift alerts, migration plans.
resource "azurerm_postgresql_flexible_server" "meta" {
  name                          = "psql-${local.name}"
  location                      = azurerm_resource_group.this.location
  resource_group_name           = azurerm_resource_group.this.name
  version                       = "16"
  sku_name                      = var.environment == "prod" ? "GP_Standard_D2ds_v5" : "B_Standard_B1ms"
  storage_mb                    = 32768
  backup_retention_days         = var.environment == "prod" ? 35 : 7
  public_network_access_enabled = false
  authentication {
    active_directory_auth_enabled = true
    password_auth_enabled         = false
    tenant_id                     = data.azurerm_client_config.current.tenant_id
  }
  lifecycle {
    ignore_changes = [zone]
  }
  tags = local.tags
}

resource "azurerm_postgresql_flexible_server_database" "platform" {
  name      = "platform"
  server_id = azurerm_postgresql_flexible_server.meta.id
  charset   = "UTF8"
  collation = "en_US.utf8"
}
