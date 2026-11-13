variable "region" {
  type    = string
  default = "eu-central-1"
}

variable "bucket_name" {
  description = "Globally unique private public-ready snapshot bucket name"
  type        = string
}

variable "publisher_principal_arn" {
  description = "Exact existing IAM role allowed to assume the snapshot publishing role"
  type        = string
}

variable "reader_principal_arn" {
  description = "Exact existing IAM role allowed to assume the server-side snapshot reader role"
  type        = string
}

variable "create_raw_bucket" {
  description = "Optional separate raw storage. Keep false for the local-first workflow."
  type        = bool
  default     = false
}
