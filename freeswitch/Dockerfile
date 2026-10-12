FROM signalwire/freeswitch:1.10.10-release

# Copy custom configuration files
COPY conf/ /etc/freeswitch/

EXPOSE 5060/udp 5060/tcp 8021/tcp 8086/tcp

CMD ["freeswitch", "-nc", "-nonat"]
