import gzip, boto3
from botocore.config import Config

c = boto3.client(
    "s3",
    endpoint_url="http://rustfs:9000",
    aws_access_key_id="elyssa",
    aws_secret_access_key="elyssa_s3_2026",
    config=Config(signature_version="s3v4"),
    region_name="us-east-1",
)

resp = c.get_object(Bucket="imdb-source", Key="title.akas.tsv.gz")
headers = 0
bad_header_pos = []
i = 0
with gzip.GzipFile(fileobj=resp["Body"], mode="rb") as g:
    for line in g:
        i += 1
        if line.startswith(b"titleId\tordering"):
            headers += 1
            bad_header_pos.append(i)
print(f"total_lines={i:,} header_occurrences={headers} positions={bad_header_pos[:10]}")
