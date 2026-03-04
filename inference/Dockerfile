FROM vllm/vllm-openai:latest

WORKDIR /app

COPY config.yaml .
COPY start.sh .
RUN chmod +x start.sh

EXPOSE 8300

ENTRYPOINT ["/bin/bash", "start.sh"]
