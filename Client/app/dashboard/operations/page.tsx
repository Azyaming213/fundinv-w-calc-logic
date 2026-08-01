'use client';

import Card from '../../components/Card';
import AuthGuard from '../../components/AuthGuard';
import { CLAIMS } from '../../lib/appconstants';

export default function OperationsDashboard() {
  return (
    <AuthGuard allowedClaims={[CLAIMS.readAllFundFlows]}>
      <OperationsDashboardContent />
    </AuthGuard>
  );
}

function OperationsDashboardContent() {
  return (
    <div className="max-w-6xl mx-auto px-8 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-fundinv-primary">Operations Console</h1>
        <p className="text-sm text-fundinv-muted mt-1">Review fund subscriptions, redemptions, and verified cash movements</p>
      </div>

      <div className="grid grid-cols-1 gap-4 mb-6">
        <Card>
          <div className="py-2">
            <div className="flex items-center gap-3 mb-3">
              <div className="w-10 h-10 bg-blue-50 rounded-lg flex items-center justify-center">
                <svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <div>
                <p className="text-sm font-medium text-fundinv-primary">Fund Flows</p>
                <p className="text-xs text-fundinv-muted">Review and process subscription/redemption requests</p>
              </div>
            </div>
            <a
              href="/dashboard/operations/fund-flows"
              className="text-sm text-fundinv-accent hover:underline"
            >
              View Fund Flows →
            </a>
          </div>
        </Card>
      </div>

      <Card title="Workflow">
        <div className="py-4 space-y-4">
          <div className="flex items-start gap-3">
            <div className="w-6 h-6 rounded-full bg-amber-100 text-amber-700 flex items-center justify-center text-xs font-bold shrink-0 mt-0.5">1</div>
            <div>
              <p className="text-sm font-medium text-fundinv-primary">Investor submits request</p>
              <p className="text-xs text-fundinv-muted">Request appears as <span className="font-mono text-amber-600">pending_ops_team</span>. Review the request details.</p>
            </div>
          </div>
          <div className="flex items-start gap-3">
            <div className="w-6 h-6 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center text-xs font-bold shrink-0 mt-0.5">2</div>
            <div>
              <p className="text-sm font-medium text-fundinv-primary">Review the fund-flow request</p>
              <p className="text-xs text-fundinv-muted">For demo PayNow subscriptions, compare the requested and received amounts. Manual transfers retain a separate approval step.</p>
            </div>
          </div>
          <div className="flex items-start gap-3">
            <div className="w-6 h-6 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center text-xs font-bold shrink-0 mt-0.5">3</div>
            <div>
              <p className="text-sm font-medium text-fundinv-primary">Verify settlement, then complete</p>
              <p className="text-xs text-fundinv-muted">Use Verify & Complete once for a matching demo PayNow receipt. In manual mode, complete only after independently verifying the bank movement. Units change only at this point.</p>
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
}
