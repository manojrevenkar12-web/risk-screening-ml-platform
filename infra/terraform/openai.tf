# Azure OpenAI in two regions. The screening tagger runs on provisioned throughput in the primary region, with
# pay-as-you-go deployments of the same model in both regions for spillover. Analyst tools and developers get their
# own deployments so their use can never take capacity from the pipeline.
locals {
  openai_regions = { primary = var.location, secondary = var.secondary_openai_location }
}

resource "azurerm_cognitive_account" "openai" {
  for_each                      = local.openai_regions
  name                          = "oai-${local.name}-${each.key}"
  location                      = each.value
  resource_group_name           = azurerm_resource_group.this.name
  kind                          = "OpenAI"
  sku_name                      = "S0"
  custom_subdomain_name         = "oai-${local.name}-${each.key}"
  local_auth_enabled            = false
  public_network_access_enabled = true
  identity {
    type = "SystemAssigned"
  }
  tags = local.tags
}

resource "azurerm_cognitive_deployment" "tagger_ptu" {
  name                 = "screening-tagger"
  cognitive_account_id = azurerm_cognitive_account.openai["primary"].id
  model {
    format  = "OpenAI"
    name    = var.tagger_model.name
    version = var.tagger_model.version
  }
  sku {
    name     = "ProvisionedManaged"
    capacity = var.ptu_units
  }
  # A retirement must never upgrade this deployment silently: the platform migrates through its gate.
  version_upgrade_option = "NoAutoUpgrade"
}

resource "azurerm_cognitive_deployment" "tagger_spill" {
  for_each             = local.openai_regions
  name                 = "screening-tagger-spill"
  cognitive_account_id = azurerm_cognitive_account.openai[each.key].id
  model {
    format  = "OpenAI"
    name    = var.tagger_model.name
    version = var.tagger_model.version
  }
  sku {
    name     = "Standard"
    capacity = var.payg_capacity_thousands_tpm
  }
  version_upgrade_option = "NoAutoUpgrade"
}

resource "azurerm_cognitive_deployment" "shared" {
  for_each             = { "analyst-assist" = 60, "sandbox" = 20 }
  name                 = each.key
  cognitive_account_id = azurerm_cognitive_account.openai["primary"].id
  model {
    format  = "OpenAI"
    name    = var.tagger_model.name
    version = var.tagger_model.version
  }
  sku {
    name     = "Standard"
    capacity = each.value
  }
  version_upgrade_option = "OnceCurrentVersionExpired"
}
