subscription_id = "00000000-0000-0000-0000-000000000000"
environment     = "dev"
alert_email     = "ml-platform@example.com"
ptu_units       = 10
team_groups = {
  analysts = { object_id = "11111111-1111-1111-1111-111111111111", deployments = ["analyst-assist"] }
  ml_dev   = { object_id = "22222222-2222-2222-2222-222222222222", deployments = ["sandbox"] }
}
