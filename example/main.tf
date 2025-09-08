module "lambda_saver" {
  source = ".."

  timezone = "Asia/Tokyo"
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

  lifecycle {
    ignore_changes = [
      tags["LastRequestedConcurrency"]
    ]
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
