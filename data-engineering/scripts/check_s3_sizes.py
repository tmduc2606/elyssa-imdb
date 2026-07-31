import boto3
from botocore.config import Config

c = boto3.client(
    "s3",
    endpoint_url="http://rustfs:9000",
    aws_access_key_id="elyssa",
    aws_secret_access_key="elyssa_s3_2026",
    config=Config(signature_version="s3v4"),
    region_name="us-east-1",
)
for f in ["title.basics.tsv.gz", "title.akas.tsv.gz", "title.principals.tsv.gz", "name.basics.tsv.gz"]:
    r = c.head_object(Bucket="imdb-source", Key=f)
    print(f"{f}: {r['ContentLength']:,} bytes, etag={r.get('ETag', '?')[:20]}")
