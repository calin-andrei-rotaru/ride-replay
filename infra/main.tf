locals {
  buckets = merge({ snapshots = var.bucket_name }, var.create_raw_bucket ? { raw = "${var.bucket_name}-raw" } : {})
}

resource "aws_s3_bucket" "private" {
  for_each      = local.buckets
  bucket        = each.value
  force_destroy = false
}

resource "aws_s3_bucket_public_access_block" "private" {
  for_each                = aws_s3_bucket.private
  bucket                  = each.value.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "private" {
  for_each = aws_s3_bucket.private
  bucket   = each.value.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "private" {
  for_each = aws_s3_bucket.private
  bucket   = each.value.id
  versioning_configuration {
    status = "Enabled"
  }
}

data "aws_iam_policy_document" "tls_only" {
  for_each = aws_s3_bucket.private
  statement {
    sid       = "DenyInsecureTransport"
    effect    = "Deny"
    actions   = ["s3:*"]
    resources = [each.value.arn, "${each.value.arn}/*"]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "tls_only" {
  for_each = aws_s3_bucket.private
  bucket   = each.value.id
  policy   = data.aws_iam_policy_document.tls_only[each.key].json
}

data "aws_iam_policy_document" "publisher_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "AWS"
      identifiers = [var.publisher_principal_arn]
    }
  }
}

resource "aws_iam_role" "publisher" {
  name_prefix        = "ride-replay-publish-"
  assume_role_policy = data.aws_iam_policy_document.publisher_trust.json
}

data "aws_iam_policy_document" "publish_snapshot" {
  statement {
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.private["snapshots"].arn}/public-ready/snapshot.json"]
  }
}

resource "aws_iam_role_policy" "publisher" {
  role   = aws_iam_role.publisher.id
  policy = data.aws_iam_policy_document.publish_snapshot.json
}

data "aws_iam_policy_document" "reader_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "AWS"
      identifiers = [var.reader_principal_arn]
    }
  }
}

resource "aws_iam_role" "reader" {
  name_prefix        = "ride-replay-read-"
  assume_role_policy = data.aws_iam_policy_document.reader_trust.json
}

data "aws_iam_policy_document" "read_snapshot" {
  statement {
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.private["snapshots"].arn}/public-ready/snapshot.json"]
  }
}

resource "aws_iam_role_policy" "reader" {
  role   = aws_iam_role.reader.id
  policy = data.aws_iam_policy_document.read_snapshot.json
}
