@scans_bp.route('/')
def run_scan_view():
    # render the page with recent scan data
    scans = get_recent_scans()
    return render_template('scans.html', recent_scans=scans)

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
