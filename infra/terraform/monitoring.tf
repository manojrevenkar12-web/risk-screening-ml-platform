resource "azurerm_monitor_action_group" "platform" {
  name                = "ag-${local.name}"
  resource_group_name = azurerm_resource_group.this.name
  short_name          = "mlplatform"
  email_receiver {
    name          = "ml-platform"
    email_address = var.alert_email
  }
  tags = local.tags
}

# Documents arrive faster than they leave: the scorer is behind (KEDA should already be scaling).
resource "azurerm_monitor_metric_alert" "backlog" {
  name                = "documents-backlog-${local.name}"
  resource_group_name = azurerm_resource_group.this.name
  scopes              = [azurerm_eventhub_namespace.this.id]
  description         = "Incoming documents exceed outgoing for 30 minutes."
  severity            = 2
  frequency           = "PT5M"
  window_size         = "PT30M"
  dynamic_criteria {
    metric_namespace  = "Microsoft.EventHub/namespaces"
    metric_name       = "IncomingMessages"
    aggregation       = "Total"
    operator          = "GreaterThan"
    alert_sensitivity = "Medium"
  }
  action {
    action_group_id = azurerm_monitor_action_group.platform.id
  }
  tags = local.tags
}

# The tagger is being throttled: spillover should be absorbing it; if this fires, add units or quota.
resource "azurerm_monitor_metric_alert" "throttling" {
  for_each            = local.openai_regions
  name                = "openai-throttling-${each.key}-${local.name}"
  resource_group_name = azurerm_resource_group.this.name
  scopes              = [azurerm_cognitive_account.openai[each.key].id]
  description         = "Azure OpenAI answers 429 to a material share of calls."
  severity            = 2
  frequency           = "PT5M"
  window_size         = "PT15M"
  criteria {
    metric_namespace = "Microsoft.CognitiveServices/accounts"
    metric_name      = "AzureOpenAIRequests"
    aggregation      = "Total"
    operator         = "GreaterThan"
    threshold        = 500
    dimension {
      name     = "StatusCode"
      operator = "Include"
      values   = ["429"]
    }
  }
  action {
    action_group_id = azurerm_monitor_action_group.platform.id
  }
  tags = local.tags
}
