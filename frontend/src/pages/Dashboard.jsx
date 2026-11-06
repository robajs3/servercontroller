import { useSession } from '../session.jsx';
import StatusCard from '../components/StatusCard.jsx';
import CameraSnap from '../components/CameraSnap.jsx';
import PingChart from '../components/PingChart.jsx';
import ServerCard from '../components/ServerCard.jsx';
import ResourcesChart from '../components/ResourcesChart.jsx';

export default function Dashboard() {
  const { main_name, camera_enabled, agents } = useSession();
  return (
    <>
      <StatusCard name={main_name} />
      {camera_enabled && <CameraSnap />}
      <PingChart />
      {agents.map(a => <ServerCard key={a.key} agent={a} />)}
      {agents.length > 0 && <ResourcesChart agents={agents} />}
    </>
  );
}
