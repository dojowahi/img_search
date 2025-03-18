python bulk_prepare.py /path/to/your/images --output bulk_upload.json
curl -X POST -F 'file=@rugs.json' http://localhost:8000/api/v1/bulk_upload/

# Execute cloud proxy on local
./cloud-sql-proxy gen-ai-4all:us-central1:img-vector

# SA impersonation
gcloud iam service-accounts add-iam-policy-binding \
  sa@my-project-id.iam.gserviceaccount.com \
  --member="user:admin@winkwink.altostrat.com" \
  --role="roles/iam.serviceAccountTokenCreator"

# Deployment
nohup sh /home/ankurwahi/python_dev/img_search/app/scripts/deploy.sh > deployment.log 2>&1 &