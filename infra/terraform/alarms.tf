# CloudWatch alarms for safe ECS operation. SNS topic optional; add notifications as needed.
# Local/dev: no ALB/ECS/RDS/WAF resources, so alarms are no-op or created only when resources exist.

# ----- ALB -----
resource "aws_cloudwatch_metric_alarm" "alb_5xx_rate" {
  alarm_name          = "${local.name}-alb-5xx"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "HTTPCode_Target_5XX_Count"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "Sum"
  threshold           = 10
  alarm_description   = "ALB target 5xx responses (sum over 1 min)"
  dimensions = {
    LoadBalancer = aws_lb.main.arn_suffix
  }
}

resource "aws_cloudwatch_metric_alarm" "alb_target_response_time" {
  alarm_name          = "${local.name}-alb-target-response-time"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "TargetResponseTime"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "Average"
  threshold           = 3
  alarm_description   = "ALB target average response time (seconds)"
  dimensions = {
    LoadBalancer = aws_lb.main.arn_suffix
  }
}

# ----- ECS (task restarts / unhealthy) -----
# Alarm when running task count is below desired (indicates restarts or failed deployments)
resource "aws_cloudwatch_metric_alarm" "ecs_task_count_low" {
  alarm_name          = "${local.name}-ecs-tasks-low"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 2
  metric_name         = "RunningTaskCount"
  namespace           = "AWS/ECS"
  period              = 60
  statistic           = "Average"
  threshold           = var.ecs_desired_count
  alarm_description   = "ECS running task count below desired (restarts or failures)"
  dimensions = {
    ClusterName = aws_ecs_cluster.main.cluster_name
    ServiceName = aws_ecs_service.backend.name
  }
}

# ----- RDS -----
resource "aws_cloudwatch_metric_alarm" "rds_cpu" {
  alarm_name          = "${local.name}-rds-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = 60
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "RDS CPU utilization high"
  dimensions = {
    DBInstanceIdentifier = aws_db_instance.main.id
  }
}

resource "aws_cloudwatch_metric_alarm" "rds_free_storage_low" {
  alarm_name          = "${local.name}-rds-storage-low"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 1
  metric_name         = "FreeStorageSpace"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 2e9 # 2 GB in bytes
  alarm_description   = "RDS free storage below 2 GB"
  dimensions = {
    DBInstanceIdentifier = aws_db_instance.main.id
  }
}

# ----- WAF (only when WAF is enabled) -----
resource "aws_cloudwatch_metric_alarm" "waf_blocked_spike" {
  count               = var.enable_waf ? 1 : 0
  alarm_name          = "${local.name}-waf-blocked-spike"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "BlockedRequests"
  namespace           = "AWS/WAFV2"
  period              = 300
  statistic           = "Sum"
  threshold           = 100
  alarm_description   = "WAF blocked requests spike (sum over 5 min)"
  dimensions = {
    WebACL = aws_wafv2_web_acl.main[0].name
    Region = var.aws_region
  }
}
