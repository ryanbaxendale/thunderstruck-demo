import webapp2
from google.appengine.api import memcache

class MainPage(webapp2.RequestHandler):
	def get(self):
		self.response.headers['Content-Type'] = 'text/plain'
		memclient = memcache.Client()

		# set the otp value
		setotp = self.request.get("setotp", None)
		if setotp is not None:
			memclient.set("setotp", setotp, namespace='brute_otp')
			otp_guess_count = 0
			memclient.set("otp_guess_count", otp_guess_count, namespace='brute_otp')
			otp_guess_max = pow(10, len(setotp))
			memclient.set("otp_guess_max", otp_guess_max, namespace='brute_otp')

		# get the current stored OTP
		target_otp = memclient.get("setotp", namespace='brute_otp')
		if target_otp is not None:
			self.response.write("Stored OTP: "+str(target_otp)+"\n")
		else:
			self.response.write("Stored OTP: None\n")

		# check if the OTP guess is correct
		otp = self.request.get("otp", None)
		if otp is None:
			self.response.write("Enter the OTP in the parameter 'otp'\n")
		else:
			memcache.incr("otp_guess_count", delta=1, namespace='brute_otp')
			if otp == target_otp:
				self.response.write("Success the correct OTP is: "+otp+"\n")
			elif otp is not None:
				self.response.write('OTP is wrong, try again\n')

		# check how many OTP have been guessed
		otp_guess_count = memclient.get("otp_guess_count", namespace='brute_otp')
		otp_guess_max = memclient.get("otp_guess_max", namespace='brute_otp')
		self.response.write("otp guessed: "+str(otp_guess_count)+"/"+str(otp_guess_max)+"\n")	

app = webapp2.WSGIApplication([
    ('/', MainPage),
], debug=False)

