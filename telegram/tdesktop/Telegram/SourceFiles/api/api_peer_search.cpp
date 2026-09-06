/*
This file is part of Telegram Desktop,
the official desktop application for the Telegram messaging service.

For license and copyright information please follow this link:
https://github.com/telegramdesktop/tdesktop/blob/master/LEGAL
*/
#include "api/api_peer_search.h"

#include "api/api_single_message_search.h"
#include "apiwrap.h"
#include "data/data_peer.h"
#include "data/data_session.h"
#include "dialogs/ui/chat_search_in.h" // IsHashOrCashtagSearchQuery
#include "main/main_session.h"
#include "puregram/puregram_whitelist.h" // Puregram: filter discovery results

namespace Api {
namespace {

constexpr auto kMinSponsoredQueryLength = 4;

// Puregram: global username search shows people always; channels, groups and
// bots only when the policy lets them open (POLICY_SPEC §4).
[[nodiscard]] bool PolicyShows(not_null<PeerData*> peer) {
	return (peer->isUser() && !peer->isBot())
		|| Puregram::Rules::Instance().canOpen(peer);
}

} // namespace

PeerSearch::PeerSearch(not_null<Main::Session*> session, Type type)
: _session(session)
, _type(type) {
}

PeerSearch::~PeerSearch() {
	clear();
}

void PeerSearch::request(
		const QString &query,
		Fn<void(PeerSearchResult)> callback,
		RequestType type) {
	using namespace Dialogs;
	_query = Api::ConvertPeerSearchQuery(query);
	_callback = callback;
	if (_query.isEmpty()
		|| IsHashOrCashtagSearchQuery(_query) != HashOrCashtag::None) {
		finish(PeerSearchResult{});
		return;
	}
	auto &cache = _cache[_query];
	if (cache.peersReady && cache.sponsoredReady) {
		finish(cache.result);
		return;
	} else if (type == RequestType::CacheOnly) {
		_callback = nullptr;
		return;
	} else if (cache.requested) {
		return;
	}
	cache.requested = true;
	cache.result.query = _query;
	if (_query.size() < kMinSponsoredQueryLength) {
		cache.sponsoredReady = true;
	} else if (_type == Type::WithSponsored) {
		requestSponsored();
	}
	requestPeers();
}

void PeerSearch::requestPeers() {
	if (!Puregram::kGlobalSearchEnabled) {
		// Puregram: contacts.search is how a channel or bot is found by name.
		// Filtering what came back still meant asking, so we do not ask.
		crl::on_main(_session, [=] {
			finishPeers(0, PeerSearchResult());
		});
		return;
	}
	const auto requestId = _session->api().request(MTPcontacts_Search(
		MTP_flags(0),
		MTP_string(_query),
		MTP_int(SearchPeopleLimit)
	)).done([=](const MTPcontacts_Found &result, mtpRequestId requestId) {
		const auto &data = result.data();
		_session->data().processUsers(data.vusers());
		_session->data().processChats(data.vchats());
		auto parsed = PeerSearchResult();
		parsed.my.reserve(data.vmy_results().v.size());
		for (const auto &id : data.vmy_results().v) {
			const auto peer = _session->data().peer(peerFromMTP(id));
			if (PolicyShows(peer)) {
				parsed.my.push_back(peer);
			}
		}
		parsed.peers.reserve(data.vresults().v.size());
		for (const auto &id : data.vresults().v) {
			const auto peer = _session->data().peer(peerFromMTP(id));
			if (PolicyShows(peer)) {
				parsed.peers.push_back(peer);
			}
		}
		finishPeers(requestId, std::move(parsed));
	}).fail([=](const MTP::Error &error, mtpRequestId requestId) {
		finishPeers(requestId, PeerSearchResult{});
	}).send();
	_peerRequests.emplace(requestId, _query);
}

void PeerSearch::requestSponsored() {
	const auto requestId = _session->api().request(
		MTPcontacts_GetSponsoredPeers(MTP_string(_query))
	).done([=](
			const MTPcontacts_SponsoredPeers &result,
			mtpRequestId requestId) {
		result.match([&](const MTPDcontacts_sponsoredPeersEmpty &) {
			finishSponsored(requestId, PeerSearchResult{});
		}, [&](const MTPDcontacts_sponsoredPeers &data) {
			_session->data().processUsers(data.vusers());
			_session->data().processChats(data.vchats());
			auto parsed = PeerSearchResult();
			parsed.sponsored.reserve(data.vpeers().v.size());
			for (const auto &peer : data.vpeers().v) {
				const auto &data = peer.data();
				const auto peerId = peerFromMTP(data.vpeer());
				const auto found = _session->data().peer(peerId);
				if (!PolicyShows(found)) {
					continue; // Puregram: sponsored peers follow the same rule.
				}
				parsed.sponsored.push_back({
					.peer = found,
					.randomId = data.vrandom_id().v,
					.sponsorInfo = TextWithEntities::Simple(
						qs(data.vsponsor_info().value_or_empty())),
					.additionalInfo = TextWithEntities::Simple(
						qs(data.vadditional_info().value_or_empty())),
				});
			}
			finishSponsored(requestId, std::move(parsed));
		});
	}).fail([=](const MTP::Error &error, mtpRequestId requestId) {
		finishSponsored(requestId, PeerSearchResult{});
	}).send();
	_sponsoredRequests.emplace(requestId, _query);
}

void PeerSearch::finishPeers(
		mtpRequestId requestId,
		PeerSearchResult result) {
	const auto query = _peerRequests.take(requestId);
	Assert(query.has_value());

	auto &cache = _cache[*query];
	cache.peersReady = true;
	cache.result.my = std::move(result.my);
	cache.result.peers = std::move(result.peers);
	if (cache.sponsoredReady && _query == *query) {
		finish(cache.result);
	}
}

void PeerSearch::finishSponsored(
		mtpRequestId requestId,
		PeerSearchResult result) {
	const auto query = _sponsoredRequests.take(requestId);
	Assert(query.has_value());

	auto &cache = _cache[*query];
	cache.sponsoredReady = true;
	cache.result.sponsored = std::move(result.sponsored);
	if (cache.peersReady && _query == *query) {
		finish(cache.result);
	}
}

void PeerSearch::finish(PeerSearchResult result) {
	if (const auto onstack = base::take(_callback)) {
		onstack(std::move(result));
	}
}

void PeerSearch::clear() {
	_query = QString();
	_callback = nullptr;
	_cache.clear();
	for (const auto &[requestId, query] : base::take(_peerRequests)) {
		_session->api().request(requestId).cancel();
	}
	for (const auto &[requestId, query] : base::take(_sponsoredRequests)) {
		_session->api().request(requestId).cancel();
	}
}

} // namespace Api
