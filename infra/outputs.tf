output "snapshot_bucket" {
  value = aws_s3_bucket.private["snapshots"].id
}

output "publisher_role_arn" {
  value = aws_iam_role.publisher.arn
}

output "reader_role_arn" {
  value = aws_iam_role.reader.arn
}
