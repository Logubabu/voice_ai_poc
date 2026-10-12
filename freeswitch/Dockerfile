# ==============================================================================
# Production FreeSWITCH 1.10 Container
# Built on Ubuntu 22.04 LTS with mod_esl, mod_sofia, mod_audio_stream
# ==============================================================================
FROM bytedesk/freeswitch:latest

# FreeSWITCH runtime environment defaults (no hard-coded passwords)
ENV BAIDU_MRCP_ENABLE=0 \
    DISABLE_IPV6=true \
    FREESWITCH_RTP_START=16384 \
    FREESWITCH_RTP_END=32768

# Ensure symlink from /etc/freeswitch to actual configuration directory
RUN mkdir -p /usr/local/freeswitch/etc/freeswitch /etc && \
    ln -sfn /usr/local/freeswitch/etc/freeswitch /etc/freeswitch

# Copy custom configuration files (event_socket, dialplan) into both paths
COPY conf/ /usr/local/freeswitch/etc/freeswitch/
COPY conf/ /etc/freeswitch/

# Health check verifying FreeSWITCH process and ESL connectivity
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD fs_cli -x "status" | grep -q "UP" || exit 1

# Expose required telephony ports:
# 5060/udp, 5060/tcp - SIP Signaling
# 8021/tcp          - ESL (Internal Docker Network only)
# 8086/tcp          - FreeSWITCH Audio Stream
EXPOSE 5060/udp 5060/tcp 8021 8086

CMD ["freeswitch", "-nf", "-nonat"]
