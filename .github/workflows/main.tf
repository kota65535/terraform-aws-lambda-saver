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
    temporary = {
      source  = "kota65535/temporary"
      version = "1.0.1"
    }
  }
  required_version = "~> 1.11.0"
}

provider "aws" {
  region = "ap-northeast-1"
}

module "lambda_saver" {
  source = "../../"
}

data "aws_iam_policy_document" "assume_role" {
  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }

    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "lambda" {
  name               = "lambda-test"
  assume_role_policy = data.aws_iam_policy_document.assume_role.json
}

resource "aws_lambda_function" "lambda" {
  filename         = data.archive_file.lambda.output_path
  function_name    = "test"
  role             = aws_iam_role.lambda.arn
  handler          = "index.handler"
  source_code_hash = data.archive_file.lambda.output_base64sha256
  runtime          = "nodejs20.x"
  publish          = true

  tags = {
    AutoStartTime = 10
    AutoStopTime  = 11
    Project       = "test"
  }
}

data "archive_file" "lambda" {
  type                    = "zip"
  source_content_filename = "index.js"
  source_content          = <<EOT
exports.handler = async (event) => {
    console.log("Event: ", event);
    return {
        statusCode: 200,
        body: JSON.stringify('Hello from Lambda!'),
    };
};
EOT
  output_path             = "${path.module}/lambda/function.zip"
}