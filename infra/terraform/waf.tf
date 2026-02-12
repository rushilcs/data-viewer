# WAF (prod): rate-based rule + AWS Managed Rules. Set enable_waf=false for staging if desired.
resource "aws_wafv2_web_acl" "main" {
  count       = var.enable_waf ? 1 : 0
  name        = local.name
  description = "Rate limit and common rule set for API ALB"
  scope       = "REGIONAL"

  default_action {
    allow {}
  }

  # Rate-based: 2000 requests per 5 min per IP (tune for prod)
  rule {
    name     = "RateLimit"
    priority = 1
    action {
      block {}
    }
    statement {
      rate_based_statement {
        limit              = 2000
        aggregate_key_type = "IP"
      }
    }
  }

  # AWS Managed Rules - common rule set (SQLi, XSS, etc.)
  rule {
    name     = "AWSManagedRulesCommonRuleSet"
    priority = 2
    override_action {
      none {}
    }
    statement {
      managed_rule_group_statement {
        vendor_name = "AWS"
        name        = "AWSManagedRulesCommonRuleSet"
      }
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name               = local.name
    sampled_requests_enabled   = true
  }
}

resource "aws_wafv2_web_acl_association" "main" {
  count        = var.enable_waf ? 1 : 0
  resource_arn = aws_lb.main.arn
  web_acl_arn  = aws_wafv2_web_acl.main[0].arn
}
