import LegalChatInterface from '@/components/LegalChatInterface';
import LegalDisclaimer from '@/components/LegalDisclaimer';

export default function Home() {
  return (
    <div className="h-screen flex flex-col bg-gray-50">
      <LegalDisclaimer />
      <LegalChatInterface />
    </div>
  );
}