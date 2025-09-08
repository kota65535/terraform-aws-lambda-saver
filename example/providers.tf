terraform {
  backend "s3" {
    bucket       = "terraform-backend-561678142736"
    region       = "ap-northeast-1"
    key          = "terraform-aws-lambda-saver.tfstate"
    use_lockfile = true
  }
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "5.96.0"
    }
  }
  required_version = "~> 1.11.0"
}

provider "aws" {
  region = "ap-northeast-1"
}

