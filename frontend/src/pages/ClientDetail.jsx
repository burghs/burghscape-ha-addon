import { useParams } from "react-router-dom";
import { ArrowLeft, Globe, Database, Clock, Users, Zap } from "lucide-react";

export default function ClientDetail() {
  const { id } = useParams();
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <a href="/clients" className="text-gray-400 hover:text-gray-600"><ArrowLeft className="w-5 h-5" /></a>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Daniel Burton</h1>
          <p className="text-gray-500 text-sm">daniel@example.com</p>
        </div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="card text-center">
          <Globe className="w-8 h-8 mx-auto text-brand-500 mb-2" />
          <p className="text-sm text-gray-500">Portal URL</p>
          <p className="font-medium text-sm">daniel.mybeacon.co.za</p>
        </div>
        <div className="card text-center">
          <Zap className="w-8 h-8 mx-auto text-yellow-500 mb-2" />
          <p className="text-sm text-gray-500">Tier</p>
          <p className="font-medium">Standard (R499/mo)</p>
        </div>
        <div className="card text-center">
          <Clock className="w-8 h-8 mx-auto text-green-500 mb-2" />
          <p className="text-sm text-gray-500">Hours Used</p>
          <p className="font-medium">0.5h / 2h</p>
        </div>
      </div>
      <div className="card">
        <h2 className="font-semibold mb-4">Home Assistant Instances</h2>
        <p className="text-gray-500 text-sm">Client has 2 instances configured.</p>
      </div>
    </div>
  );
}
