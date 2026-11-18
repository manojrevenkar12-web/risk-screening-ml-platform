# The data lake: raw documents, deduplicated and scored partitions, labels, golden sets and model artefacts.
resource "azurerm_storage_account" "lake" {
  name                            = "st${local.flat}lake"
  location                        = azurerm_resource_group.this.location
  resource_group_name             = azurerm_resource_group.this.name
  account_tier                    = "Standard"
  account_replication_type        = "ZRS"
  account_kind                    = "StorageV2"
  is_hns_enabled                  = true
  min_tls_version                 = "TLS1_2"
  shared_access_key_enabled       = false
  allow_nested_items_to_be_public = false
  tags                            = local.tags
}

resource "azurerm_storage_data_lake_gen2_filesystem" "zones" {
  for_each           = toset(["raw", "curated", "labels", "golden", "models"])
  name               = each.key
  storage_account_id = azurerm_storage_account.lake.id
}

resource "azurerm_storage_management_policy" "lake" {
  storage_account_id = azurerm_storage_account.lake.id
  rule {
    name    = "raw-to-cool"
    enabled = true
    filters {
      prefix_match = ["raw/"]
      blob_types   = ["blockBlob"]
    }
    actions {
      base_blob {
        tier_to_cool_after_days_since_modification_greater_than = 30
        delete_after_days_since_modification_greater_than       = 400
      }
    }
  }
}

# Azure ML wants its own storage account without hierarchical namespace.
resource "azurerm_storage_account" "aml" {
  name                     = "st${local.flat}aml"
  location                 = azurerm_resource_group.this.location
  resource_group_name      = azurerm_resource_group.this.name
  account_tier             = "Standard"
  account_replication_type = "LRS"
  min_tls_version          = "TLS1_2"
  tags                     = local.tags
}

resource "azurerm_container_registry" "this" {
  name                = "cr${local.flat}"
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  sku                 = "Standard"
  admin_enabled       = false
  tags                = local.tags
}
