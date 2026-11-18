variable "subscription_id" {
  type        = string
  description = "Azure subscription that holds the screening platform."
}

variable "environment" {
  type        = string
  description = "dev, staging or prod."
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be dev, staging or prod."
  }
}

variable "prefix" {
  type        = string
  default     = "rscreen"
  description = "Short prefix for resource names (lowercase letters and digits)."
}

variable "location" {
  type        = string
  default     = "germanywestcentral"
  description = "Primary region: AKS, Event Hubs, storage, Azure ML and the primary Azure OpenAI account."
}

variable "secondary_openai_location" {
  type        = string
  default     = "swedencentral"
  description = "Second Azure OpenAI region; throttled pay-as-you-go calls spill over here."
}

variable "scorer_vm_size" {
  type        = string
  default     = "Standard_D4s_v5"
  description = "Node size of the pool that runs the relevance scorer."
}

variable "scorer_nodes" {
  type        = object({ min = number, max = number })
  default     = { min = 1, max = 12 }
  description = "Cluster-autoscaler bounds for the scorer pool; KEDA scales pods inside them."
}

variable "tagger_model" {
  type        = object({ name = string, version = string })
  default     = { name = "gpt-4o-mini", version = "2024-07-18" }
  description = "Model behind the screening-tagger deployments. Changed by a gated migration, never by hand."
}

variable "ptu_units" {
  type        = number
  default     = 10
  description = "Provisioned throughput for the tagger in the primary region (the planner's cost-optimal number)."
}

variable "payg_capacity_thousands_tpm" {
  type        = number
  default     = 750
  description = "Pay-as-you-go quota per region for spillover, in thousands of tokens per minute."
}

variable "team_groups" {
  type        = map(object({ object_id = string, deployments = list(string) }))
  default     = {}
  description = "Entra ID groups and the deployments their members may call through the gateway."
}

variable "alert_email" {
  type        = string
  description = "Where platform alerts go."
}

variable "tags" {
  type    = map(string)
  default = { owner = "ml-platform", system = "risk-screening" }
}
