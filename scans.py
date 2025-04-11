scans_bp = Blueprint('scans', __name__, url_prefix='/scans')

@scans_bp.route('/')
def run_scan_view():
    # In production, you'd probably pull recent scan data here
    return render_template('scans.html', recent_scans=[])

@scans_bp.route('/run', methods=['POST'])
def run_scan():
    # get form data and start scan (e.g., subprocess or celery job)
    ...
    return redirect(url_for('scans.run_scan_view'))

@scans_bp.route('/history')
def scan_history():
    # show full scan history
    ...

@scans_bp.route('/report/<int:scan_id>')
def view_report(scan_id):
    # show scan report
    ...
