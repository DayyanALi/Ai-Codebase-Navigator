

provider "aws" {
  region = var.aws_region
}

module "template_files" {
  source   = "hashicorp/dir/template"
  base_dir = "${path.module}/frontend/dist"
}

resource "aws_s3_bucket" "hosting_bucket" {
  bucket = var.bucket_name
}

resource "aws_s3_bucket_public_access_block" "disable_block" {
  bucket = aws_s3_bucket.hosting_bucket.id

  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

resource "aws_s3_bucket_policy" "hosting_bucket_policy" {
  bucket = aws_s3_bucket.hosting_bucket.id  

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect    = "Allow",
        Principal = "*",
        Action    = "s3:GetObject",
        Resource  = "${aws_s3_bucket.hosting_bucket.arn}/*"
      }
    ]
  })

  depends_on = [aws_s3_bucket_public_access_block.disable_block]
}

resource "aws_s3_bucket_website_configuration" "hosting_bucket_website" {
  bucket = aws_s3_bucket.hosting_bucket.id

  index_document {
    suffix = "index.html"
  }

  error_document {
    key = "error.html"
  }
}

resource "aws_s3_object" "hosting_files" {
  for_each = module.template_files.files

  bucket       = aws_s3_bucket.hosting_bucket.id
  key          = each.key
  source       = each.value.source_path
  content_type = each.value.content_type
  etag         = each.value.digests.md5
}

output "website_url" {
  value = aws_s3_bucket_website_configuration.hosting_bucket_website.website_endpoint
}






# provider "aws" {
#   region = var.aws_region
# }

# resource "aws_instance" "backend" {
#   ami                    = "ami-0c02fb55956c7d316"  # Amazon Linux 2
#   instance_type          = "t2.micro"
#   # subnet_id              = var.public_subnet_id
#   # vpc_security_group_ids = var.vpc_security_group_ids
#   key_name               = var.key_pair_name
#   associate_public_ip_address = true

#   # 1️⃣ Copy local ./backend folder to /home/ec2-user/backend
#   provisioner "file" {
#     source      = "${path.module}/backend/"
#     destination = "/home/ec2-user/backend/"

#     connection {
#       type        = "ssh"
#       user        = "ec2-user"
#       host        = self.public_ip
#       private_key = file(var.private_key_path)
#     }
#   }

#   # 2️⃣ SSH in and install / start the Flask app
#   provisioner "remote-exec" {
#     inline = [
#       "sudo yum update -y",
#       "sudo yum install -y python3 git",
#       "sudo yum install -y python3-pip",
#       "pip install --upgrade pip",
#       "pip install -r requirements.txt",
#       "cd backend",
#       "python3 server.py"
#     ]

#     connection {
#       type        = "ssh"
#       user        = "ec2-user"
#       host        = self.public_ip
#       private_key = file(var.private_key_path)
#     }
#   }

#   tags = {
#     Name = "FlaskBackend"
#   }
# }

# output "backend_public_ip" {
#   value = aws_instance.backend.public_ip
# }
