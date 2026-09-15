def popup(self, viewPath, viewParams = {}, popupTitle = ''):

	if self.page.props.dimensions.viewport.width < 1000:
		# mobile popup
		mobilePosition = {"width": "100%", "height": "100%"}
		system.perspective.openPopup(
			'mobile-popup-%s' % str(self.view.params)
			, viewPath
			, params=viewParams
			, title=popupTitle
			, position=mobilePosition
			, showCloseIcon=True
			, resizable=False
			, draggable=False
			, modal=True
			, viewportBound=True
		)
	else:
		# desktop popup
		system.perspective.openPopup(
			'fullsize-popup-%s' % str(self.view.params)
			, viewPath
			, params=viewParams
			, title=popupTitle
			, showCloseIcon=True
			, resizable=True
			, draggable=True
			, modal=False
			, viewportBound=False
		)