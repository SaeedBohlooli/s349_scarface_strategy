


log_info() {
	  echo "$(date '+%Y-%m-%d %H:%M:%S') [INFO ] $1"
}

log_info "-------------------"
log_info "Starting restart ...."
log_info "Calling stop ..."

log_info "Starting IBG ...."

cd /opt/ibc
xvfb-run -a ./gatewaystart.sh  -inline

log_info "IBG started ...."
