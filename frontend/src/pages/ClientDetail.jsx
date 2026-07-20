import { useParams } from "react-router-dom";
import { ArrowLeft, Globe, Clock, Zap } from "lucide-react";
import { Card } from "../components/ui";

export default function ClientDetail() {
  const { id } = useParams();
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <a href="/clients" className="text-muted-text transition hover:text-white"><ArrowLeft className="h-5 w-5" /></a>
        <div>
          <h1 className="text-2xl font-bold text-white">Daniel Burton</h1>
          <p className="text-gray-400 text-sm">daniel@example.com</p>
        </div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="text-center">
          <Globe className="mx-auto mb-2 h-8 w-8 text-primary-text" />
          <p className="text-sm text-gray-400">Portal URL</p>
          <p className="font-medium text-sm">daniel.mybeacon.co.za</p>
        </Card>
        <Card className="text-center">
          <Zap className="mx-auto mb-2 h-8 w-8 text-warning-text" />
          <p className="text-sm text-gray-400">Tier</p>
          <p className="font-medium">Standard (R499/mo)</p>
        </Card>
        <Card className="text-center">
          <Clock className="mx-auto mb-2 h-8 w-8 text-success-text" />
          <p className="text-sm text-gray-400">Hours Used</p>
          <p className="font-medium">0.5h / 2h</p>
        </Card>
      </div>
      <Card>
        <h2 className="mb-4 font-semibold text-white">Home Assistant Instances</h2>
        <p className="text-gray-400 text-sm">Client has 2 instances configured.</p>
      </Card>
    </div>
  );
}
