output "aks_name" {
  value = azurerm_kubernetes_cluster.this.name
}

output "workload_client_ids" {
  value       = { for k, v in azurerm_user_assigned_identity.workload : k => v.client_id }
  description = "Annotate each Kubernetes service account with its client id (azure.workload.identity/client-id)."
}

output "eventhubs_kafka_endpoint" {
  value = "${azurerm_eventhub_namespace.this.name}.servicebus.windows.net:9093"
}

output "openai_endpoints" {
  value = { for k, v in azurerm_cognitive_account.openai : k => v.endpoint }
}

output "aml_workspace" {
  value = azurerm_machine_learning_workspace.this.name
}

output "lake" {
  value = azurerm_storage_account.lake.primary_dfs_endpoint
}
