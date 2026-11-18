# Event Hubs speaks the Kafka protocol: producers and the scorer use Kafka clients; KEDA scales on consumer lag.
resource "azurerm_eventhub_namespace" "this" {
  name                          = "evhns-${local.name}"
  location                      = azurerm_resource_group.this.location
  resource_group_name           = azurerm_resource_group.this.name
  sku                           = "Standard"
  capacity                      = 2
  auto_inflate_enabled          = true
  maximum_throughput_units      = 10
  local_authentication_enabled  = false
  public_network_access_enabled = true
  tags                          = local.tags
}

resource "azurerm_eventhub" "topics" {
  for_each          = { "documents-raw" = 16, "documents-unique" = 16, "documents-relevant" = 8, "documents-tagged" = 8 }
  name              = each.key
  namespace_id      = azurerm_eventhub_namespace.this.id
  partition_count   = each.value
  message_retention = 7
}

resource "azurerm_eventhub_consumer_group" "scorer" {
  name                = "relevance-scorer"
  namespace_name      = azurerm_eventhub_namespace.this.name
  eventhub_name       = azurerm_eventhub.topics["documents-unique"].name
  resource_group_name = azurerm_resource_group.this.name
}

resource "azurerm_eventhub_consumer_group" "tagger" {
  name                = "llm-tagger"
  namespace_name      = azurerm_eventhub_namespace.this.name
  eventhub_name       = azurerm_eventhub.topics["documents-relevant"].name
  resource_group_name = azurerm_resource_group.this.name
}
