import discord, time, json, sys, shlex, asyncio
from hashlib import sha256
from random import choice, randrange
from math import floor

def stringtime(secs):
	amts = {1: "second", 60: "minute", 3600: "hour"}
	times = []
	for i in sorted(amts)[::-1]:
		amt = floor(secs / i)
		secs -= amt * i
		if not amt: continue
		times.append("{} {}{}".format(amt, amts[i], "s" if amt != 1 else ""))
	if times:
		if len(times) > 1:
			last = times.pop()
			return "{} and {}".format(", ".join(times), last)
		else:
			return times[0]
	else:
		return "no time"
		
def intervals():
	n = 0
	while True:
		ints = [60*1, 60*2, 60*5, 60*10, 60*30]
		if n < 5:
			yield ints[n]
		else:
			yield 3600 * (n - 4)
		n += 1
		
class JsonStorage():
	def __init__(self, filename):
		self.filename = filename
	def read(self):
		try:
			f = open(self.filename)
			data = json.load(f)
			return data
		except:
			print("Couldn't read save data.")
		finally:
			f.close()
	def write(self, data):
		f = open(self.filename, "w")
		json.dump(data, f)
		f.close()
		
class ChallengePool():
	def __init__(self, amt=5, filename="pool.dat"):
		self.amt = 5
		self.store = JsonStorage(filename)
		self.challenges = {}
		self.votes = {}
		try:
			self.load()
		except:
			print("Failed to load challenge pool on init")
		self.fill()
	def generate(self):
		keys = "A Bb B C C# D Eb E F F# G Ab".split()
		scales = "minor major".split()
		genres = "70s music|80s music|90s music|vaporwave|hip hop|future bass|dubstep|trap|neuro|jazz|future funk|chiptune|cinematic|minimal|chill".split("|")
		challenge = "{} in {} {} at {}bpm".format(choice(genres), choice(keys), choice(scales), randrange(60, 220, 2))
		chalk = sha256(challenge.encode()).hexdigest()[:4]
		if chalk in self.challenges:
			self.generate()
		else:
			self.challenges[chalk] = challenge
	def fill(self):
		amt = self.amt - len(self.challenges)
		if amt < 0:
			self.challenges = dict((i, self.challenges[i]) for i in list(self.challenges)[:5])
			return
		for i in range(amt):
			self.generate()
		self.votes = dict((i, self.votes[i]) for i in self.votes if self.votes[i] in self.challenges)
		self.save()
	def save(self):
		self.store.write(self.challenges)
	def load(self):
		self.challenges = self.store.read()
	def vote(self, challenge, user):
		if challenge in self.challenges:
			self.votes[user.id] = challenge
		else:
			raise
	def __str__(self):
		agnv = list(self.votes[i] for i in self.votes)
		msg = ["challenge ideas:", ""]
		msg += list("**{}** {} *({} votes)*".format(i, self.challenges[i], agnv.count(i)) for i in self.challenges)
		return "\n".join(msg)

class Buttchan():
	def __init__(self, interface, loop = asyncio.get_event_loop(), filename = "botchan.dat"):
		self.interface = interface
		self.sessid = sha256(str(time.time()).encode()).hexdigest()[:16]
		self.last_id = 0
		self.loop = loop
		self.pool = ChallengePool()
		self.running = {}
		self.challenges = {}
		self.storage = JsonStorage(filename)
		try: self.load()
		except: print("Failed to load Buttchan's stored data on init")
		print("Buttchan with id {} made".format(self.sessid))
	def load(self):
		self.last_id, data, interfacedata = self.storage.read()
		self.interface.buttload(interfacedata)
		for i in data:
			self.challenges[i] = Challenge(self, 0, "")
			self.challenges[i].load(data[i])
	def save(self):
		challenges = {}
		for i in self.challenges:
			challenges[i] = self.challenges[i].save()
		data = [self.last_id, challenges, self.interface.buttsave()]
		self.storage.write(data)
	def challenge(self, *challenges):
		chid = []
		for i in challenges:
			self.challenges[str(self.last_id)] = Challenge(self, str(self.last_id), *i)
			print("Created challenge #{}.".format(self.last_id))
			chid.append(str(self.last_id))
			self.last_id += 1
		self.save()
		return chid

class Challenge():
	def __init__(self, butt, id, desc, duration=3600, grace=600, vote=600, start=time.time()):
		self.butt = butt
		self.id = id
		self.running = False
		self.winner = butt.interface.user
		self.desc = desc
		self.duration = duration
		self.stages = [duration, grace, vote]
		self.stagenames = ["challenge", "upload", "voting"]
		self.stage = 0
		self.start = start
		self.getintervals()
		self.jointimes = {}
		
		self.entries = {}
		self.participants = []
		self.votes = {}
	
	def load(self, loadable):
		self.running = loadable["running"]
		if "winner" in loadable:
			self.winner = self.butt.interface.buttchannel.server.get_member(loadable["winner"])
		else:
			self.winner = self.butt.interface.user
		self.desc = loadable["desc"]
		self.duration = loadable["duration"]
		self.stages = [self.duration, loadable["grace"], loadable["vote"]]
		self.stage = loadable["stage"]
		self.start = loadable["start"]
		self.entries = loadable["entries"]
		self.votes = loadable["votes"]
		self.jointimes = loadable["jointimes"]
		self.participants = list(self.butt.interface.get_member(i) for i in loadable["participants"])
		
	def save(self):
		loadable = {}
		loadable["running"] = self.running
		try:
			loadable["winner"] = self.winner.id
		except:
			pass
		loadable["desc"] = self.desc
		loadable["duration"] = self.duration
		loadable["grace"] = self.stages[1]
		loadable["vote"] = self.stages[2]
		loadable["stage"] = self.stage
		loadable["start"] = self.start
		loadable["jointimes"] = self.jointimes
		loadable["entries"] = self.entries
		loadable["votes"] = self.votes
		loadable["participants"] = list(i.id for i in self.participants)
		return loadable
		
	def getintervals(self):
		self.intervals = [0]
		for i in intervals():
			if i >= self.duration:
				break
			self.intervals.append(i)
		self.intervals.append(self.duration)
		
	def __str__(self):
		info = ["**Challenge #{}** *({}".format(self.id, [
			"not running",
			"running",
			"upload stage",
			"voting stage",
			"won by " + self.winner.name if self.winner else "nobody"
		][self.running + self.stage])]
		if 0 <= self.stage <3 and self.running:
			info[-1] += ", {} remaining)*".format(stringtime(self.start + self.duration - time.time()))
		else:
			info[-1] += "*)"
		info.append(self.desc)
		if not self.running: return "\n".join(info)
		
		info.append("")
		if self.stage == 0:
			if self.participants:
				info.append("Participants: " + ", ".join(i.name for i in self.participants))
			else:
				info.append("Participants: *None yet*")
		else:
			for i in self.participants:
				if i.id in self.entries:
					info.append("{}: {}".format(i.name, self.entries[i.id]))
					if self.stage > 1:
						info[-1] += " *({} votes)*".format(
							list(self.votes[i] for i in self.votes).count(i.id)
						)
				else:
					info.append("{}: *No entry*".format(i.name))
		if self.stage == 3:
			info.append("")
			info.append("**Won by {}!**".format(self.winner.name))
		return "\n".join(info)
	
	async def run(self):
		self.running = True
		self.start = time.time()
		await self.butt.interface.send_message(self.butt.interface.buttchannel,
			"Starting challenge #{}".format(self.id))
		self.butt.save()
		while self.stage <3:
			elapsed = time.time() - self.start
			remaining = self.duration - elapsed
			wait = remaining - self.intervals[-1]
			await asyncio.sleep(wait)
			remaining = self.intervals.pop()
			if remaining:
				await self.butt.interface.send_message(self.butt.interface.buttchannel,
					"**Challenge #{}** *({} stage)* ~ {} remaining.".format(
					self.id, self.stagenames[self.stage], stringtime(remaining))
				)
			if not self.intervals:
				self.stage += 1
				if self.stage == 3:
					agnv = list(self.votes[i] for i in self.votes)
					winner_id = sorted(self.participants, key=lambda x:agnv.count(x))[-1]
					self.winner = self.butt.interface.buttchannel.server.get_member(winner_id)
					await self.butt.interface.send_message(self.butt.interface.buttchannel,
						"Challenge #{} is over! {} wins!".format(self.id, self.winner.mention))
					continue
				self.duration = self.stages[self.stage]
				self.start = time.time()
				self.getintervals()
				self.butt.save()
			
class ButtDiscord(discord.Client):
	def __init__(self):
		super().__init__()
		self.buttchan = None
		self.buttchannel = None
	def buttsave(self):
		return self.buttchannel.id
	def buttload(self, data):
		self.buttchannel = self.get_channel(data)
	async def on_ready(self):
		self.buttchan = Buttchan(self)
	async def on_message(self, message):
		if message.content.startswith("%"):
			args = shlex.split(message.content[1:])
			command = args.pop(0).lower()
		else: return
		if not self.buttchannel:
			if command == "id":
				await self.send_message(message.channel, self.buttchan.sessid)
			if command == "here" and args == [self.buttchan.sessid]:
				self.buttchannel = message.channel
				print("Buttchan {} is now in channel {}".format(self.buttchan.sessid, message.channel.id))
				await self.send_message(message.channel, choice(sass[0]))
			return
			
		if command == "help":
			msg = ["{} {}my id: `{}`".format(message.author.mention, choice(sass[1]), self.buttchan.sessid)]
			msg += ["",
				"`%help` display this message",
				"`%challenge <id>` display challenge information",
				"`%imin <id>` enter a challenge",
				"`%submit <id>` submit your entry",
				"`%vote <id> <@user>` vote for a user's entry",
				"`%pool` view the challenges pool",
				"`%poolvote <id>` vote for a challenge in the pool",
				"`%makechallenge [id] [duration]` create a challenge from the pool *(mods only)*",
				"`%start <id>` start a challenge *(mods only)*",
				"`%replace <pool #>` replace a challenge in the pool *(mods only)*",
				"`%delete <id>` delete a challenge *(mods only)*"]
			await self.send_message(message.channel, "\n".join(msg))
			
		if command == "challenge":
			if args:
				if args[0] in self.buttchan.challenges:
					msg = ["{} {}".format(message.author.mention, str(self.buttchan.challenges[args[0]]))]
				else:
					msg = ["{} {}".format(message.author.mention, choice(sass[3]))]
			else:
				msg = ["{} {}".format(message.author.mention, choice(sass[2])), ""]
				msg += list(str(self.buttchan.challenges[i]).split("\n")[0] for i in self.buttchan.challenges)
				if not self.buttchan.challenges:
					msg += ["i don't have any challenges at the moment..."]
			await self.send_message(message.channel, "\n".join(msg))
			
		if command == "imin":
			if args:
				if args[0] in self.buttchan.challenges:
					challenge = self.buttchan.challenges[args[0]]
					if message.author in challenge.participants:
						msg = ["{} {}".format(message.author.mention, choice(sass[5]))]
					else:
						if challenge.stage == 0:
							challenge.participants.append(message.author)
							challenge.jointimes[message.author.id] = time.time()
							msg = ["{} {}".format(message.author.mention, choice(sass[7]))]
							if challenge.running:
								msg[-1] += " ~ you have {} tho".format(stringtime(challenge.duration + challenge.start - time.time()))
						else:
							msg = ["{} {}".format(message.author.mention, choice(sass[8]))]
				else:
					msg = ["{} {}".format(message.author.mention, choice(sass[4]))]
			else:
				msg = ["{} {}".format(message.author.mention, choice(sass[6]))]
			await self.send_message(message.channel, "\n".join(msg))
				
		if command == "submit":
			if args:
				if args[0] in self.buttchan.challenges:
					challenge = self.buttchan.challenges[args[0]]
					if challenge.stage == 1:
						challenge.entries[message.author.id] = args[1]
						msg = ["{} your entry has been counted <3".format(message.author.mention)]
					else:
						msg = ["{} you can only submit during the upload stage".format(message.author.mention)]
				else:
					msg = ["{} {}".format(message.author.mention, choice(sass[3]))]
			else:
				msg = ["{} {}".format(message.author.mention, choice(sass[6]))]
			await self.send_message(message.channel, "\n".join(msg))
			self.buttchan.save()
				
		if command == "vote":
			if args:
				if args[0] in self.buttchan.challenges:
					challenge = self.buttchan.challenges[args[0]]
					vote_id = args[1][2:-1]
					if vote_id in challenge.participants:
						if challenge.stage == 2:
							challenge.votes[message.author.id] = vote_id
							msg = ["{} your vote has been counted <3".format(message.author.mention)]
						else:
							msg = ["{} you can only vote during the voting stage".format(message.author.mention)]
					else:
						msg = ["{} that person doesn't exist it seems".format(message.author.mention)]
				else:
					msg = ["{} {}".format(message.author.mention, choice(sass[3]))]
			else:
				msg = ["{} {}".format(message.author.mention, choice(sass[6]))]
			await self.send_message(message.channel, "\n".join(msg))
			self.buttchan.save()
				
		if command == "start":
			if not self.admincheck(message.author):
				msg = ["{} {}".format(message.author.mention, choice(sass[10]))]
			elif args:
				if args[0] in self.buttchan.challenges:
					challenge = self.buttchan.challenges[args[0]]
					self.buttchan.running[args[0]] = self.buttchan.loop.create_task(challenge.run())
				else:
					msg = ["{} {}".format(message.author.mention, choice(sass[3]))]
			else:
				msg = ["{} {}".format(message.author.mention, choice(sass[6]))]
			try:
				await self.send_message(message.channel, "\n".join(msg))
			except: pass
			self.buttchan.save()
				
		if command == "replace":
			if not self.admincheck(message.author):
				msg = ["{} {}".format(message.author.mention, choice(sass[10]))]
			elif args:
				if args[0] in self.buttchan.pool.challenges:
					del self.buttchan.pool.challenges[args[0]]
					self.buttchan.pool.fill()
					msg = ["{} made a new thingy for ya".format(message.author.mention)]
				else:
					msg = ["{} {}".format(message.author.mention, choice(sass[3]))]
			else:
				msg = ["{} {}".format(message.author.mention, choice(sass[6]))]
			try:
				await self.send_message(message.channel, "\n".join(msg))
			except: pass
				
		if command == "delete":
			if not self.admincheck(message.author):
				msg = ["{} {}".format(message.author.mention, choice(sass[10]))]
			elif args:
				if args[0] in self.buttchan.challenges:
					try:
						self.buttchan.running[args[0]].stop()
						del self.buttchan.running[args[0]]
					except: pass
					del self.buttchan.challenges[args[0]]
					msg = ["{} rip that challenge".format(message.author.mention)]
				else:
					msg = ["{} {}".format(message.author.mention, choice(sass[3]))]
			else:
				msg = ["{} {}".format(message.author.mention, choice(sass[6]))]
			try:
				await self.send_message(message.channel, "\n".join(msg))
			except: pass
			self.buttchan.save()
			
		if command == "pool":
			await self.send_message(message.channel, str(self.buttchan.pool))
			
		if command == "poolvote":
			if args:
				try:
					self.buttchan.pool.vote(args[0], message.author)
					msg = ["{} your vote has been counted <3".format(message.author.mention)]
				except:
					msg = ["{} {}".format(message.author.mention, choice(sass[3]))]
			else:
				msg = ["{} {}".format(message.author.mention, choice(sass[6]))]
			await self.send_message(message.channel, "\n".join(msg))
			self.buttchan.save()
				
		if command == "makechallenge":
			if not self.admincheck(message.author):
				msg = ["{} {}".format(message.author.mention, choice(sass[10]))]
				await self.send_message(message.channel, "\n".join(msg))
				return
			agnv = list(self.buttchan.pool.votes[i] for i in self.buttchan.pool.votes)
			highest_challenge = sorted(self.buttchan.pool.challenges, key=lambda x:agnv.count(x))[-1]
			highest_challenge = self.buttchan.pool.challenges[highest_challenge]
			if args:
				if args[0] in self.buttchan.pool.challenges:
					challenge = self.buttchan.pool.challenges[args[0]]
					if len(args) > 1:
						try:
							chid = self.buttchan.challenge([challenge, float(args[1])])
							msg = ["{} made challenge *{}*".format(message.author.mention, chid[0])]
						except:
							msg = ["{} that aint a number ;~;".format(message.author.mention)]
					else:
						chid = self.buttchan.challenge([challenge])
						msg = ["{} made challenge *{}*".format(message.author.mention, chid[0])]
				else:
					msg = ["{} {}".format(message.author.mention, choice(sass[3]))]
			else:
				chid = self.buttchan.challenge([highest_challenge])
				msg = ["{} made challenge *{}*".format(message.author.mention, chid[0])]
			await self.send_message(message.channel, "\n".join(msg))
			self.buttchan.save()
			
	def admincheck(self, user):
		return self.buttchannel.permissions_for(user).kick_members
				
sass = [
	"hai ;3|oh hello|bbs :D|sup hoes".split("|"),
	"you fuckin know who i am~ |isn't my name obvious enough...|i'm a buttchan! ".split("|"),
	"here's a list of timewasters for you:|these challenges are lit|i'll challenge you~|*siiiigh*".split("|"),
	"there's no challenge like that|check your spelling pls bb|woah hold up, dunno what that is lol|bruh...noooo".split("|"),
	"you can't join a nonexistent challenge|why don't you *make* that challenge first...|sorry eh, that one doesn't exist, can't put you in it".split("|"),
	"you're already in that sweetie|you're in that one...|you can't enter twice you goon".split("|"),
	"you gotta tell me what challenge you're talking about|woah woah i need some id|what challenge tho".split("|"),
	"added you <3|you're innnn|gl :D|have fuuuun bb :D you're in".split("|"),
	"that challenge isn't in a joinable stage|that one's like...over already...|*i cannot turn back time*".split("|"),
	"chek ur fuggin privlig|you ain't no staff member last i checked|get somebody who knows what they're doing to do that".split("|")]
		
if __name__ == "__main__":
	interface = ButtDiscord()
	interface.run(*sys.argv[1:])
