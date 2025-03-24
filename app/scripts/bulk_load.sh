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

#AlloyDB AUth proxy

wget https://storage.googleapis.com/alloydb-auth-proxy/v1.13.0/alloydb-auth-proxy.linux.amd64 -O alloydb-auth-proxy
chmod +x alloydb-auth-proxy
./alloydb-auth-proxy --public-ip  projects/gen-ai-4all/locations/us-central1/clusters/alloy-img-vector/instances/alloy-img-vector-primary
