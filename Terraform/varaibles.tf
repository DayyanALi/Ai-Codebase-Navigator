variable "aws_region" {
    description = "AWS Region"
    type = string
}

variable "bucket_name" {
    description = "S3 Bucket Name"
    type = string
}

# variable "public_subnet_id" { type = string }
# variable "vpc_security_group_ids" { type = list(string) }
variable "key_pair_name"    { type = string }    # already uploaded EC2 key pair name
variable "private_key_path" { type = string }    # path to your .pem on your workstation
